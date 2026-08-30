import torch
import torch.nn as nn
import lightgbm as lgb
from sklearn.linear_model import LogisticRegression
import numpy as np

# ==========================================
# 1. Monotonic Multi-Horizon Loss & Heads
# ==========================================
# We want P(1h) <= P(6h) <= P(24h) <= P(72h) <= P(168h).
# Instead of predicting raw probabilities per head, we predict the *conditional hazard* 
# or incremental probability of recovering in that specific interval, 
# and cumulate them (like discrete survival analysis).
# Interval 0: 0-1h
# Interval 1: 1-6h
# Interval 2: 6-24h
# Interval 3: 24-72h
# Interval 4: 72-168h
# The network outputs logits for each interval: P(recover in interval | didn't recover before).

class MonotonicMultiHorizonHead(nn.Module):
    def __init__(self, in_features, num_horizons=5):
        super().__init__()
        self.num_horizons = num_horizons
        self.head = nn.Linear(in_features, num_horizons)
        
    def forward(self, x):
        logits = self.head(x)
        # Convert logits to discrete hazard rates (probability of event in interval given survival up to interval)
        hazards = torch.sigmoid(logits)
        
        # Calculate cumulative probability of NOT recovering (survival)
        survival = torch.cumprod(1.0 - hazards, dim=1)
        
        # P(recovery by horizon t) = 1 - S(t)
        # This guarantees P(t1) <= P(t2)
        cdf = 1.0 - survival
        return cdf

def binary_cross_entropy_multi_horizon(preds_cdf, targets_cdf):
    # preds_cdf: (B, H), targets_cdf: (B, H) (1 if recovered by H, else 0)
    # We can just use standard BCE on the CDF since it's bounded [0, 1]
    # To avoid vanishing gradients, BCE on cumprod can be tricky, but works fine for small horizons (5).
    loss = nn.BCELoss()(preds_cdf, targets_cdf)
    return loss

# ==========================================
# 2. PyTorch Temporal GRU
# ==========================================
class TemporalGRU(nn.Module):
    def __init__(self, seq_features, hidden_dim=64, num_layers=1, num_horizons=5):
        super().__init__()
        self.gru = nn.GRU(input_size=seq_features, hidden_size=hidden_dim, 
                          num_layers=num_layers, batch_first=True)
        self.head = MonotonicMultiHorizonHead(hidden_dim, num_horizons)
        
    def forward(self, seq_x, return_embeds=False):
        # seq_x: (Batch, SeqLen, Features)
        out, h_n = self.gru(seq_x)
        # Use the last hidden state for prediction
        embeds = h_n[-1] # (Batch, Hidden)
        if return_embeds:
            return embeds
        return self.head(embeds)

# ==========================================
# 3. Challenger: Compact Transformer
# ==========================================
class CompactTransformer(nn.Module):
    def __init__(self, seq_features, hidden_dim=64, num_heads=4, num_layers=1, num_horizons=5):
        super().__init__()
        self.input_proj = nn.Linear(seq_features, hidden_dim)
        encoder_layer = nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=num_heads, 
                                                   dim_feedforward=hidden_dim*2, batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.head = MonotonicMultiHorizonHead(hidden_dim, num_horizons)
        
    def forward(self, seq_x, return_embeds=False):
        # seq_x: (Batch, SeqLen, Features)
        x = self.input_proj(seq_x)
        out = self.transformer(x)
        # Mean pooling over sequence
        embeds = out.mean(dim=1)
        if return_embeds:
            return embeds
        return self.head(embeds)

# ==========================================
# 4. PyTorch Hybrid (Tabular MLP + GRU)
# ==========================================
class HybridModel(nn.Module):
    def __init__(self, tab_features, seq_features, tab_hidden=64, seq_hidden=64, num_horizons=5):
        super().__init__()
        self.tab_mlp = nn.Sequential(
            nn.Linear(tab_features, tab_hidden),
            nn.ReLU(),
            nn.Linear(tab_hidden, tab_hidden)
        )
        self.gru = TemporalGRU(seq_features, seq_hidden, num_horizons=num_horizons)
        
        # Fusion
        self.fusion = nn.Sequential(
            nn.Linear(tab_hidden + seq_hidden, tab_hidden),
            nn.ReLU(),
        )
        self.head = MonotonicMultiHorizonHead(tab_hidden, num_horizons)
        
    def forward(self, tab_x, seq_x):
        tab_emb = self.tab_mlp(tab_x)
        seq_emb = self.gru(seq_x, return_embeds=True)
        fused = torch.cat([tab_emb, seq_emb], dim=1)
        fused = self.fusion(fused)
        return self.head(fused)

# ==========================================
# 5. Baseline wrappers
# ==========================================
class SklearnMultiHorizonWrapper:
    def __init__(self, model_class, **kwargs):
        # One model per horizon for baselines
        self.models = [model_class(**kwargs) for _ in range(5)]
        
    def fit(self, X, y_matrix):
        # y_matrix is (N, 5)
        for i in range(5):
            self.models[i].fit(X, y_matrix[:, i])
            
    def predict_proba(self, X):
        preds = []
        for i in range(5):
            preds.append(self.models[i].predict_proba(X)[:, 1])
        preds = np.column_stack(preds)
        # Force monotonicity via isotonic repair (max accumulation)
        return np.maximum.accumulate(preds, axis=1)

def get_logistic_baseline():
    return SklearnMultiHorizonWrapper(LogisticRegression, max_iter=1000)

def get_lightgbm_baseline():
    return SklearnMultiHorizonWrapper(lgb.LGBMClassifier, n_estimators=100, learning_rate=0.05, n_jobs=-1)

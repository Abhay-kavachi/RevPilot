import os
import json
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ml.features import FeatureSchema

def main():
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'prod_model')
    os.makedirs(out_dir, exist_ok=True)
    
    metadata = {
        "model_version": "LightGBM_Prod_v1.0",
        "feature_schema_version": FeatureSchema.version,
        "horizons": FeatureSchema.horizons,
        "features": FeatureSchema.features,
        "expected_count": FeatureSchema.expected_count,
        "calibration_version": "isotonic_1.0",
        "dataset_version": "world_model_events_seed42",
        "world_model_version": "2.0"
    }
    
    with open(os.path.join(out_dir, 'metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
        
    print("Patched artifact with metadata.json")

if __name__ == "__main__":
    main()

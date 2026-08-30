import os
import json
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ml.features import FeatureSchema

def main():
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'prod_model')
    os.makedirs(out_dir, exist_ok=True)
    
    metadata = {
        "version": FeatureSchema.version,
        "features": FeatureSchema.features,
        "horizons": FeatureSchema.horizons,
        "expected_count": FeatureSchema.expected_count
    }
    
    with open(os.path.join(out_dir, 'metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
        
    print("Patched artifact with metadata.json")

if __name__ == "__main__":
    main()

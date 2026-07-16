#!/usr/bin/env python
"""Download Excel data files from HF Dataset repo."""
from pathlib import Path
from huggingface_hub import hf_hub_download

REPO_ID = "Saerix/saerix-finance-data"
FILES = [
    "bist30_yillik_fiyatlar_2010_2025.xlsx",
    "EVDS_14-07-2026.xlsx",
]

def main():
    out_dir = Path(__file__).parent.parent / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    for fname in FILES:
        print(f"Downloading {fname}...")
        path = hf_hub_download(
            repo_id=REPO_ID,
            filename=fname,
            repo_type="dataset",
            local_dir=out_dir,
            local_dir_use_symlinks=False,
        )
        print(f"  → {path}")

    print("\nDone. Run: python src/rag_pipeline.py build")

if __name__ == "__main__":
    main()
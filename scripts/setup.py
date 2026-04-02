"""First-run setup for frenzAI."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main():
    print("=== frenzAI Setup ===\n")

    # 1. Install Python dependencies
    print("1. Installing Python dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "backend" / "requirements.txt")],
        check=True,
    )

    # 2. Install frontend dependencies
    print("\n2. Installing frontend dependencies...")
    subprocess.run(["npm", "install"], cwd=str(ROOT / "frontend"), check=True, shell=True)

    # 3. Create data directories
    print("\n3. Creating data directories...")
    for d in ["data/voices/embeddings", "data/voices/samples", "data/projects",
              "data/exports", "data/rvc_models", "data/temp"]:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    print("   Done.")

    # 4. Check GPU
    print("\n4. Checking GPU...")
    try:
        import torch
        if torch.cuda.is_available():
            print(f"   GPU: {torch.cuda.get_device_name(0)}")
            print(f"   VRAM: {torch.cuda.get_device_properties(0).total_mem // (1024**2)}MB")
        else:
            print("   No GPU detected. CPU mode will be used (LuxTTS works great on CPU).")
    except ImportError:
        print("   PyTorch not installed. Install with CUDA for GPU acceleration:")
        print("   pip install torch --index-url https://download.pytorch.org/whl/cu121")

    print("\n=== Setup Complete! ===")
    print("\nTo start:")
    print("  1. cd backend && python -m uvicorn app.main:app --port 8111")
    print("  2. cd frontend && npm run dev")
    print("  3. Open http://localhost:5173")
    print("\nTo download a model:")
    print("  python scripts/download_models.py luxtts")


if __name__ == "__main__":
    main()

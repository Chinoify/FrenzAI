"""CLI model downloader for frenzAI."""
import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.config import settings


MODELS = {
    "luxtts": {"repo": "luxai/LuxTTS", "size": "~300MB"},
    "qwen3-tts": {"repo": "Qwen/Qwen3-TTS", "size": "~3.4GB"},
    "chatterbox": {"repo": "resemble-ai/chatterbox", "size": "~2.8GB"},
    "fish-speech": {"repo": "fishaudio/fish-speech-1.5", "size": "~3.5GB"},
    "bark": {"repo": "suno/bark", "size": "~5GB"},
}


def download_model(name: str):
    if name not in MODELS:
        print(f"Unknown model: {name}")
        print(f"Available: {', '.join(MODELS.keys())}")
        return

    from huggingface_hub import snapshot_download

    model_info = MODELS[name]
    model_dir = settings.models_dir / name
    print(f"Downloading {name} ({model_info['size']}) to {model_dir}...")
    snapshot_download(
        repo_id=model_info["repo"],
        local_dir=str(model_dir),
        ignore_patterns=["*.md", "*.txt", "*.gitattributes"],
    )
    print(f"Done! {name} downloaded to {model_dir}")


def main():
    parser = argparse.ArgumentParser(description="Download frenzAI AI models")
    parser.add_argument("model", nargs="?", help="Model to download (or 'all' for all models)")
    parser.add_argument("--list", action="store_true", help="List available models")
    args = parser.parse_args()

    if args.list or not args.model:
        print("Available models:")
        for name, info in MODELS.items():
            status = "downloaded" if (settings.models_dir / name).exists() else "not downloaded"
            print(f"  {name:15s} {info['size']:>8s}  [{status}]")
        return

    if args.model == "all":
        for name in MODELS:
            download_model(name)
    else:
        download_model(args.model)


if __name__ == "__main__":
    main()

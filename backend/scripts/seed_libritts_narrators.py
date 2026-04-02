"""Download 60 real, unique narrator voices from LibriTTS-R (filtered, clean).
These are actual human audiobook readers from LibriVox - unaltered recordings.
Each speaker is a different real person with a unique voice."""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Add ffmpeg to PATH
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _project_root + os.pathsep + os.environ.get("PATH", "")

import numpy as np


async def main():
    import soundfile as sf
    from app.config import settings
    from app.db.database import get_session
    from app.db.models import Voice
    from app.db.seed import create_tables
    from sqlalchemy import select

    await create_tables()

    # Check existing narrator voices
    async for session in get_session():
        result = await session.execute(select(Voice.name).where(Voice.tags.contains('"narrator"')))
        existing = {r[0] for r in result.fetchall()}
        break

    print("Loading LibriTTS-R dataset from HuggingFace...")
    print("This downloads parquet files with real audiobook narrator recordings.")

    # Download and read parquet files
    from huggingface_hub import hf_hub_download
    import pandas as pd

    all_speakers = {}  # speaker_id -> list of (audio_data, sample_rate, text, duration)

    # Load multiple parquet files to get enough speakers
    parquet_files = [
        "clean/test.clean-00000-of-00003.parquet",
        "clean/test.clean-00001-of-00003.parquet",
        "clean/test.clean-00002-of-00003.parquet",
        "clean/dev.clean-00000-of-00004.parquet",
        "clean/dev.clean-00001-of-00004.parquet",
        "clean/dev.clean-00002-of-00004.parquet",
        "clean/dev.clean-00003-of-00004.parquet",
        "clean/train.clean.100-00000-of-00018.parquet",
        "clean/train.clean.100-00001-of-00018.parquet",
        "clean/train.clean.100-00002-of-00018.parquet",
    ]

    for pf in parquet_files:
        print(f"  Loading {pf}...")
        try:
            path = hf_hub_download(
                repo_id="parler-tts/libritts_r_filtered",
                filename=pf,
                repo_type="dataset",
            )
            df = pd.read_parquet(path)

            for _, row in df.iterrows():
                sid = str(row["speaker_id"])
                audio_data = row["audio"]

                # Audio is stored as {"bytes": b"RIFF...", "path": "...wav"}
                if not isinstance(audio_data, dict) or "bytes" not in audio_data:
                    continue

                wav_bytes = audio_data["bytes"]
                if not wav_bytes or len(wav_bytes) < 1000:
                    continue

                # Parse WAV bytes
                import io
                try:
                    samples, sr = sf.read(io.BytesIO(wav_bytes))
                    if len(samples.shape) > 1:
                        samples = samples.mean(axis=1)
                    samples = samples.astype(np.float32)
                except Exception:
                    continue

                duration = len(samples) / sr

                # Only keep samples between 8-30 seconds (good for audiobook narration)
                if duration < 8 or duration > 30:
                    continue

                if sid not in all_speakers:
                    all_speakers[sid] = []
                all_speakers[sid].append((samples, sr, row.get("text_normalized", ""), duration))

        except Exception as e:
            print(f"    Error: {e}")

        # Stop if we have enough speakers
        if len(all_speakers) >= 70:
            break

    print(f"\nFound {len(all_speakers)} unique speakers")

    # Select best sample per speaker (longest clean recording between 10-25s)
    selected = []
    for sid, recordings in all_speakers.items():
        # Sort by duration, pick the one closest to 15-20 seconds
        recordings.sort(key=lambda r: abs(r[3] - 17))
        best = recordings[0]
        selected.append((sid, best[0], best[1], best[2], best[3]))

    # Take top 60
    selected = selected[:60]
    print(f"Selected {len(selected)} speakers for narrator voices")

    # Determine gender from speaker ID (LibriTTS convention: IDs < 5000 tend to be
    # specific ranges, but we'll use a simple heuristic based on pitch analysis)
    created = 0
    for i, (sid, samples, sr, text, duration) in enumerate(selected):
        # Simple pitch-based gender detection
        zero_crossings = np.sum(np.abs(np.diff(np.sign(samples)))) / (2 * len(samples))
        gender = "female" if zero_crossings > 0.04 else "male"

        voice_id = str(uuid.uuid4())
        name = f"Narrator {sid}"

        if name in existing:
            print(f"  [{i+1}/{len(selected)}] Skip: {name} (exists)")
            continue

        # Save the audio sample UNALTERED
        wav_path = settings.samples_dir / f"{voice_id}.wav"
        sf.write(str(wav_path), samples, sr)

        # Placeholder embedding
        emb = np.zeros(256, dtype=np.float32)
        emb_path = settings.embeddings_dir / f"{voice_id}.npy"
        np.save(str(emb_path), emb)

        # Insert into DB
        async for session in get_session():
            voice = Voice(
                id=voice_id,
                name=name,
                engine="chatterbox",
                language="en",
                tags=["narrator", gender],
                notes=f"LibriTTS narrator (speaker {sid}, {gender}, {duration:.1f}s). Real audiobook recording, unaltered.",
                embedding_path=str(emb_path),
                sample_path=str(wav_path),
                quality_score=4.0,
            )
            session.add(voice)
            await session.commit()
            break

        created += 1
        print(f"  [{i+1}/{len(selected)}] Created: {name} ({gender}, {duration:.1f}s)")

    print(f"\nDone! Created {created} real narrator voices from LibriTTS-R")


if __name__ == "__main__":
    asyncio.run(main())

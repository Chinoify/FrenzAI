"""Seed ALL Edge TTS voices into FrenzAI database.
These are 400+ Microsoft neural AI voices — each genuinely unique sounding."""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _project_root + os.pathsep + os.environ.get("PATH", "")

import numpy as np


async def main():
    import edge_tts
    from pydub import AudioSegment
    from app.config import settings
    from app.db.database import get_session
    from app.db.models import Voice
    from app.db.seed import create_tables
    from sqlalchemy import select

    await create_tables()

    # Check existing
    async for session in get_session():
        result = await session.execute(select(Voice.name))
        existing = {r[0] for r in result.fetchall()}
        break

    # Get all available voices
    all_voices = await edge_tts.list_voices()
    print(f"Total Edge TTS voices available: {len(all_voices)}")

    # Language mapping for our DB
    lang_map = {
        "en-US": "en", "en-GB": "en-gb", "en-AU": "en", "en-CA": "en",
        "en-IN": "en", "en-IE": "en", "en-NZ": "en", "en-NG": "en",
        "en-PH": "en", "en-SG": "en", "en-ZA": "en", "en-KE": "en",
        "en-TZ": "en", "en-HK": "en",
        "de-DE": "de", "de-AT": "de", "de-CH": "de",
        "fr-FR": "fr", "fr-CA": "fr", "fr-BE": "fr", "fr-CH": "fr",
        "es-ES": "es", "es-MX": "es", "es-AR": "es", "es-CO": "es",
        "it-IT": "it", "pt-BR": "pt", "pt-PT": "pt",
        "hi-IN": "hi", "ja-JP": "ja", "ko-KR": "ko",
        "ar-SA": "ar", "ar-EG": "ar", "ar-AE": "ar",
        "ru-RU": "ru", "nl-NL": "nl", "pl-PL": "pl",
        "sv-SE": "sv", "tr-TR": "tr", "id-ID": "id",
        "th-TH": "th", "vi-VN": "vi",
    }

    # Country/accent tags
    accent_map = {
        "en-US": "american", "en-GB": "british", "en-AU": "australian",
        "en-CA": "canadian", "en-IN": "indian", "en-IE": "irish",
        "en-NZ": "new-zealand", "en-NG": "nigerian", "en-ZA": "south-african",
        "en-KE": "kenyan", "en-SG": "singaporean", "en-PH": "filipino",
        "en-TZ": "tanzanian", "en-HK": "hong-kong",
        "es-MX": "mexican", "es-AR": "argentinian", "es-CO": "colombian",
        "fr-CA": "canadian-french", "fr-BE": "belgian",
        "pt-BR": "brazilian", "pt-PT": "european-portuguese",
        "de-AT": "austrian", "de-CH": "swiss-german",
    }

    sample_text = "The morning sun cast long golden shadows across the ancient library."

    created = 0
    skipped = 0
    failed = 0

    for i, v in enumerate(all_voices):
        voice_code = v["ShortName"]
        locale = v["Locale"]
        gender = v.get("Gender", "Unknown").lower()
        friendly_name = v.get("FriendlyName", voice_code)

        # Create a clean display name
        # e.g. "en-US-AvaNeural" -> "Ava (US Female)"
        short = voice_code.split("-")[-1].replace("Neural", "").replace("Multilingual", " ML")
        locale_short = locale[:5]
        display_name = f"{short} ({locale_short} {gender.title()})"

        if display_name in existing:
            skipped += 1
            continue

        # Map language
        lang = lang_map.get(locale, locale[:2].lower())
        accent = accent_map.get(locale, "")
        tags = ["edge-tts", gender]
        if accent:
            tags.append(accent)

        try:
            voice_id = str(uuid.uuid4())

            # Generate sample audio
            communicate = edge_tts.Communicate(sample_text, voice_code)
            mp3_path = settings.samples_dir / f"{voice_id}.mp3"
            await communicate.save(str(mp3_path))

            # Convert to WAV
            wav_path = settings.samples_dir / f"{voice_id}.wav"
            audio = AudioSegment.from_mp3(str(mp3_path))
            audio.export(str(wav_path), format="wav")
            mp3_path.unlink(missing_ok=True)

            # Store voice code in embedding
            emb = np.zeros(256, dtype=np.float32)
            code_bytes = voice_code.encode("utf-8")
            for j, b in enumerate(code_bytes[:256]):
                emb[j] = float(b)
            emb_path = settings.embeddings_dir / f"{voice_id}.npy"
            np.save(str(emb_path), emb)

            # Insert into DB
            async for session in get_session():
                voice = Voice(
                    id=voice_id,
                    name=display_name,
                    engine="edge-tts",
                    language=lang,
                    tags=tags,
                    notes=f"Microsoft Edge TTS: {voice_code}. {friendly_name}",
                    embedding_path=str(emb_path),
                    sample_path=str(wav_path),
                    quality_score=4.0,
                )
                session.add(voice)
                await session.commit()
                break

            created += 1
            if created % 10 == 0:
                print(f"  [{created} created, {i+1}/{len(all_voices)} processed]")

        except Exception as e:
            failed += 1

    print(f"\nDone! Created: {created}, Skipped: {skipped}, Failed: {failed}")
    print(f"Total Edge TTS voices in FrenzAI: {created}")


if __name__ == "__main__":
    asyncio.run(main())

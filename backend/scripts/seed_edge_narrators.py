"""Seed 60 curated Edge TTS narrator voices into FrenzAI.
Each voice is a real, unique Microsoft neural voice — they all sound genuinely different.
Curated specifically for audiobook narration quality."""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _project_root + os.pathsep + os.environ.get("PATH", "")

import numpy as np

# 60 curated voices for audiobook narration
# Each is a REAL, UNIQUE Microsoft neural voice
NARRATOR_VOICES = [
    # === American English (16) ===
    ("Ava (US Female)", "en-US-AvaNeural", "en", "female", ["american", "narrator", "warm"]),
    ("Emma (US Female)", "en-US-EmmaNeural", "en", "female", ["american", "narrator", "clear"]),
    ("Jenny (US Female)", "en-US-JennyNeural", "en", "female", ["american", "narrator", "friendly"]),
    ("Aria (US Female)", "en-US-AriaNeural", "en", "female", ["american", "narrator", "expressive"]),
    ("Michelle (US Female)", "en-US-MichelleNeural", "en", "female", ["american", "narrator", "professional"]),
    ("Ana (US Female)", "en-US-AnaNeural", "en", "female", ["american", "narrator", "gentle"]),
    ("Andrew (US Male)", "en-US-AndrewNeural", "en", "male", ["american", "narrator", "authoritative"]),
    ("Brian (US Male)", "en-US-BrianNeural", "en", "male", ["american", "narrator", "warm"]),
    ("Christopher (US Male)", "en-US-ChristopherNeural", "en", "male", ["american", "narrator", "deep"]),
    ("Eric (US Male)", "en-US-EricNeural", "en", "male", ["american", "narrator", "clear"]),
    ("Guy (US Male)", "en-US-GuyNeural", "en", "male", ["american", "narrator", "storyteller"]),
    ("Roger (US Male)", "en-US-RogerNeural", "en", "male", ["american", "narrator", "rich"]),
    ("Steffan (US Male)", "en-US-SteffanNeural", "en", "male", ["american", "narrator", "calm"]),
    ("Ava Multilingual (US)", "en-US-AvaMultilingualNeural", "en", "female", ["american", "narrator", "multilingual"]),
    ("Andrew Multilingual (US)", "en-US-AndrewMultilingualNeural", "en", "male", ["american", "narrator", "multilingual"]),
    ("Brian Multilingual (US)", "en-US-BrianMultilingualNeural", "en", "male", ["american", "narrator", "versatile"]),
    # === British English (5) ===
    ("Libby (UK Female)", "en-GB-LibbyNeural", "en-gb", "female", ["british", "narrator", "elegant"]),
    ("Maisie (UK Female)", "en-GB-MaisieNeural", "en-gb", "female", ["british", "narrator", "young"]),
    ("Sonia (UK Female)", "en-GB-SoniaNeural", "en-gb", "female", ["british", "narrator", "classic"]),
    ("Ryan (UK Male)", "en-GB-RyanNeural", "en-gb", "male", ["british", "narrator", "warm"]),
    ("Thomas (UK Male)", "en-GB-ThomasNeural", "en-gb", "male", ["british", "narrator", "authoritative"]),
    # === Nigerian English (2) ===
    ("Ezinne (Nigerian Female)", "en-NG-EzinneNeural", "en", "female", ["nigerian", "narrator", "warm"]),
    ("Abeo (Nigerian Male)", "en-NG-AbeoNeural", "en", "male", ["nigerian", "narrator", "rich"]),
    # === Australian English (2) ===
    ("Natasha (AU Female)", "en-AU-NatashaNeural", "en", "female", ["australian", "narrator"]),
    ("William (AU Male)", "en-AU-WilliamMultilingualNeural", "en", "male", ["australian", "narrator"]),
    # === Indian English (3) ===
    ("Neerja (Indian Female)", "en-IN-NeerjaNeural", "en", "female", ["indian", "narrator"]),
    ("Neerja Expressive (Indian)", "en-IN-NeerjaExpressiveNeural", "en", "female", ["indian", "narrator", "expressive"]),
    ("Prabhat (Indian Male)", "en-IN-PrabhatNeural", "en", "male", ["indian", "narrator"]),
    # === Irish English (2) ===
    ("Emily (Irish Female)", "en-IE-EmilyNeural", "en", "female", ["irish", "narrator"]),
    ("Connor (Irish Male)", "en-IE-ConnorNeural", "en", "male", ["irish", "narrator"]),
    # === German (4) ===
    ("Katja (German Female)", "de-DE-KatjaNeural", "de", "female", ["german", "narrator"]),
    ("Amala (German Female)", "de-DE-AmalaNeural", "de", "female", ["german", "narrator", "warm"]),
    ("Conrad (German Male)", "de-DE-ConradNeural", "de", "male", ["german", "narrator"]),
    ("Florian (German Male)", "de-DE-FlorianMultilingualNeural", "de", "male", ["german", "narrator"]),
    # === French (4) ===
    ("Denise (French Female)", "fr-FR-DeniseNeural", "fr", "female", ["french", "narrator"]),
    ("Eloise (French Female)", "fr-FR-EloiseNeural", "fr", "female", ["french", "narrator", "warm"]),
    ("Henri (French Male)", "fr-FR-HenriNeural", "fr", "male", ["french", "narrator"]),
    ("Remy (French Male)", "fr-FR-RemyMultilingualNeural", "fr", "male", ["french", "narrator"]),
    # === Spanish (4) ===
    ("Elvira (Spanish Female)", "es-ES-ElviraNeural", "es", "female", ["spanish", "narrator"]),
    ("Abril (Mexican Female)", "es-MX-DaliaNeural", "es", "female", ["spanish", "narrator", "mexican"]),
    ("Alvaro (Spanish Male)", "es-ES-AlvaroNeural", "es", "male", ["spanish", "narrator"]),
    ("Jorge (Mexican Male)", "es-MX-JorgeNeural", "es", "male", ["spanish", "narrator", "mexican"]),
    # === Italian (3) ===
    ("Elsa (Italian Female)", "it-IT-ElsaNeural", "it", "female", ["italian", "narrator"]),
    ("Isabella (Italian Female)", "it-IT-IsabellaNeural", "it", "female", ["italian", "narrator", "warm"]),
    ("Diego (Italian Male)", "it-IT-DiegoNeural", "it", "male", ["italian", "narrator"]),
    # === Portuguese (3) ===
    ("Francisca (PT Female)", "pt-BR-FranciscaNeural", "pt", "female", ["portuguese", "narrator", "brazilian"]),
    ("Thalita (PT Female)", "pt-BR-ThalitaNeural", "pt", "female", ["portuguese", "narrator"]),
    ("Antonio (PT Male)", "pt-BR-AntonioNeural", "pt", "male", ["portuguese", "narrator"]),
    # === Hindi (2) ===
    ("Swara (Hindi Female)", "hi-IN-SwaraNeural", "hi", "female", ["hindi", "narrator"]),
    ("Madhur (Hindi Male)", "hi-IN-MadhurNeural", "hi", "male", ["hindi", "narrator"]),
    # === Japanese (2) ===
    ("Nanami (Japanese Female)", "ja-JP-NanamiNeural", "ja", "female", ["japanese", "narrator"]),
    ("Keita (Japanese Male)", "ja-JP-KeitaNeural", "ja", "male", ["japanese", "narrator"]),
    # === Korean (2) ===
    ("Sun-Hi (Korean Female)", "ko-KR-SunHiNeural", "ko", "female", ["korean", "narrator"]),
    ("InJoon (Korean Male)", "ko-KR-InJoonNeural", "ko", "male", ["korean", "narrator"]),
    # === Arabic (2) ===
    ("Salma (Arabic Female)", "ar-SA-ZariyahNeural", "ar", "female", ["arabic", "narrator"]),
    ("Hamed (Arabic Male)", "ar-SA-HamedNeural", "ar", "male", ["arabic", "narrator"]),
    # === South African English (2) ===
    ("Leah (SA Female)", "en-ZA-LeahNeural", "en", "female", ["south-african", "narrator"]),
    ("Luke (SA Male)", "en-ZA-LukeNeural", "en", "male", ["south-african", "narrator"]),
    # === Kenyan English (2) ===
    ("Asilia (Kenyan Female)", "en-KE-AsiliaNeural", "en", "female", ["kenyan", "narrator"]),
    ("Chilemba (Kenyan Male)", "en-KE-ChilembaNeural", "en", "male", ["kenyan", "narrator"]),
]


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

    created = 0
    skipped = 0
    failed = 0
    sample_text = "The morning sun cast long golden shadows across the ancient library. She opened the first page and began to read aloud, her voice filling the quiet room."

    for i, (name, voice_code, lang, gender, tags) in enumerate(NARRATOR_VOICES):
        if name in existing:
            skipped += 1
            print(f"  [{i+1}/{len(NARRATOR_VOICES)}] Skip: {name}")
            continue

        try:
            print(f"  [{i+1}/{len(NARRATOR_VOICES)}] Generating: {name} ({voice_code})...", end=" ", flush=True)

            voice_id = str(uuid.uuid4())

            # Generate a sample using Edge TTS
            communicate = edge_tts.Communicate(sample_text, voice_code)
            mp3_path = settings.samples_dir / f"{voice_id}.mp3"
            await communicate.save(str(mp3_path))

            # Convert to WAV (keep unaltered quality)
            wav_path = settings.samples_dir / f"{voice_id}.wav"
            audio = AudioSegment.from_mp3(str(mp3_path))
            audio.export(str(wav_path), format="wav")
            mp3_path.unlink(missing_ok=True)

            # Store voice code in embedding for retrieval
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
                    name=name,
                    engine="edge-tts",
                    language=lang,
                    tags=tags,
                    notes=f"Microsoft Edge TTS ({voice_code}). {gender.title()} narrator voice.",
                    embedding_path=str(emb_path),
                    sample_path=str(wav_path),
                    quality_score=4.5,
                )
                session.add(voice)
                await session.commit()
                break

            created += 1
            print("OK")

        except Exception as e:
            failed += 1
            print(f"FAILED: {e}")

    print(f"\nDone! Created: {created}, Skipped: {skipped}, Failed: {failed}")


if __name__ == "__main__":
    asyncio.run(main())

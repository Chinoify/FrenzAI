"""Download real unique narrator voices from LibriVox (public domain audiobooks).
Each audiobook is read by a different real person = truly unique voice."""
import asyncio
import os
import sys
import uuid
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Add project root to PATH for ffmpeg
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _project_root + os.pathsep + os.environ.get("PATH", "")

import numpy as np

# Each entry: (narrator_name, archive_id, mp3_filename, language, gender, tags)
# Every archive_id is a different LibriVox audiobook = different real narrator
REAL_NARRATORS = [
    # === English Female ===
    ("Karen Savage", "secret_garden_librivox", "secretgarden_01_burnett_64kb.mp3", "en", "female", ["american", "narrator"]),
    ("Kara Shallenberg", "prideandprejudice_0711_librivox", "pride_01_austen_64kb.mp3", "en", "female", ["american", "narrator"]),
    ("Elizabeth Klett", "janeeyre_0809_librivox", "janeeyre_01_bronte_64kb.mp3", "en", "female", ["american", "narrator"]),
    ("Cori Samuel", "northandsouth_0903_librivox", "northandsouth_01_gaskell_64kb.mp3", "en", "female", ["british", "narrator"]),
    ("Kristin Hughes", "little_women_0711_librivox", "littlewomen_01_alcott_64kb.mp3", "en", "female", ["american", "narrator"]),
    ("Annie Coleman Rothenberg", "persuasion_0710_librivox", "persuasion_01_austen_64kb.mp3", "en", "female", ["american", "narrator"]),
    ("Kara Shallenberg II", "emma_solo_librivox", "emma_01_austen_64kb.mp3", "en", "female", ["american", "narrator"]),
    ("Ruth Golding", "cranford_0803_librivox", "cranford_01_gaskell_64kb.mp3", "en", "female", ["british", "narrator"]),
    ("Tadhg", "wuthering_heights_0911_librivox", "wutheringheights_01_bronte_64kb.mp3", "en", "female", ["british", "narrator"]),
    ("Sherry Crowther", "middlemarch_0903_librivox", "middlemarch_01_eliot_64kb.mp3", "en", "female", ["american", "narrator"]),
    ("Jennifer Estep", "sense_and_sensibility_0810_librivox", "senseandsensibility_01_austen_64kb.mp3", "en", "female", ["american", "narrator"]),
    ("Leanne Yau", "anne_of_green_gables_librivox", "anneofgreengables_01_montgomery_64kb.mp3", "en", "female", ["british", "narrator"]),
    # === English Male ===
    ("Mark Smith", "moby_dick_librivox", "mobydick_001_melville_64kb.mp3", "en", "male", ["american", "narrator"]),
    ("David Wales", "tale_2_cities_librivox", "twocities_01_dickens_64kb.mp3", "en", "male", ["british", "narrator"]),
    ("Mark Nelson", "great_expectations_0810_librivox", "greatexpectations_01_dickens_64kb.mp3", "en", "male", ["american", "narrator"]),
    ("John Greenman", "huck_finn_librivox", "huckfinn_01_twain_64kb.mp3", "en", "male", ["american", "narrator"]),
    ("Adrian Praetzellis", "treasure_island_librivox", "treasureisland_01_stevenson_64kb.mp3", "en", "male", ["british", "narrator"]),
    ("Bob Neufeld", "heart_of_darkness", "heart_of_darkness_01_conrad_64kb.mp3", "en", "male", ["american", "narrator"]),
    ("David Clarke", "odyssey_butler_librivox", "odyssey_01_homer_64kb.mp3", "en", "male", ["british", "narrator"]),
    ("Peter Eastman", "divine_comedy_librivox", "divinecomedy_01_dante_64kb.mp3", "en", "male", ["american", "narrator"]),
    ("Stewart Wills", "oliver_twist_librivox", "olivertwist_01_dickens_64kb.mp3", "en", "male", ["british", "narrator"]),
    ("Chip", "sherlock_holmes_01_doyle", "holmes01_01_doyle_64kb.mp3", "en", "male", ["british", "narrator"]),
    ("Chris Goringe", "dracula_librivox", "dracula_01_stoker_64kb.mp3", "en", "male", ["british", "narrator"]),
    ("Larry Wilson", "frankenstein_librivox", "frankenstein_01_shelley_64kb.mp3", "en", "male", ["american", "narrator"]),
    ("Kevin S.", "war_of_the_worlds_librivox", "warofworlds_01_wells_64kb.mp3", "en", "male", ["american", "narrator"]),
    ("Shon Tomker", "around_world_80_days_librivox", "aroundtheworld_01_verne_64kb.mp3", "en", "male", ["american", "narrator"]),
    ("Phil Chenevert", "call_of_the_wild_librivox", "callofthewild_01_london_64kb.mp3", "en", "male", ["american", "narrator"]),
    ("Tom Crawford", "uncle_toms_cabin_librivox", "uncletomscabin_01_stowe_64kb.mp3", "en", "male", ["american", "narrator"]),
    # === German ===
    ("Hokuspokus", "verwandlung_0805_librivox", "verwandlung_01_kafka_64kb.mp3", "de", "male", ["german", "narrator"]),
    ("Gesine", "siddhartha_0805_librivox", "siddhartha_01_hesse_64kb.mp3", "de", "female", ["german", "narrator"]),
    ("Dirk Weber", "processtrial_0806_librivox", "processtrial_01_kafka_64kb.mp3", "de", "male", ["german", "narrator"]),
    ("Eva K.", "buddenbrooks_01_0902_librivox", "buddenbrooks_01_mann_64kb.mp3", "de", "female", ["german", "narrator"]),
    # === French ===
    ("Nadine Eckert-Boulet", "madame_bovary_0805_librivox", "madamebovary_01_flaubert_64kb.mp3", "fr", "female", ["french", "narrator"]),
    ("Rene Depasse", "lesmiserables_tome1_0711_librivox", "lesmiserables_t1_01_hugo_64kb.mp3", "fr", "male", ["french", "narrator"]),
    ("Christiane Jehel", "petit_prince_0712_librivox", "petitprince_01_saint-exupery_64kb.mp3", "fr", "female", ["french", "narrator"]),
    ("Pierre Bellec", "vingt_mille_lieues_0806_librivox", "20000lieues_01_verne_64kb.mp3", "fr", "male", ["french", "narrator"]),
    # === Spanish ===
    ("Tux", "lazarillo_de_tormes_0711_librivox", "lazarillo_01_anonimo_64kb.mp3", "es", "male", ["spanish", "narrator"]),
    ("Claudia Barrett", "fabulas_esopo_01_librivox", "fabulasesopo_001_esopo_64kb.mp3", "es", "female", ["spanish", "narrator"]),
    ("Josehp", "platero_y_yo_0806_librivox", "platero_01_jimenez_64kb.mp3", "es", "male", ["spanish", "narrator"]),
    ("Elo Cuico", "don_quijote_01_0711_librivox", "quijote_01_cervantes_64kb.mp3", "es", "male", ["spanish", "narrator"]),
    # === Italian ===
    ("Emanuela Luciani", "divina_commedia_inferno_librivox", "inferno_01_dante_64kb.mp3", "it", "female", ["italian", "narrator"]),
    ("Marco Calvo", "pinocchio_0805_librivox", "pinocchio_01_collodi_64kb.mp3", "it", "male", ["italian", "narrator"]),
    ("Psjock", "promessi_sposi_0806_librivox", "promessisposi_01_manzoni_64kb.mp3", "it", "male", ["italian", "narrator"]),
    # === Portuguese ===
    ("Leni", "lusiadas_0805_librivox", "lusiadas_01_camoes_64kb.mp3", "pt", "female", ["portuguese", "narrator"]),
    ("Dsjack", "dom_casmurro_0806_librivox", "domcasmurro_01_machado_64kb.mp3", "pt", "male", ["portuguese", "narrator"]),
]


async def main():
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
    failed = 0
    skipped = 0

    for name, archive_id, mp3_file, lang, gender, tags in REAL_NARRATORS:
        if name in existing:
            skipped += 1
            print(f"  [{skipped + created + failed}/{len(REAL_NARRATORS)}] Skip: {name}")
            continue

        url = f"https://archive.org/download/{archive_id}/{mp3_file}"
        voice_id = str(uuid.uuid4())
        mp3_path = settings.samples_dir / f"{voice_id}.mp3"
        wav_path = settings.samples_dir / f"{voice_id}.wav"

        try:
            print(f"  [{skipped + created + failed + 1}/{len(REAL_NARRATORS)}] Downloading: {name} ({lang}, {gender})...", end=" ", flush=True)

            # Download with retry and delay
            import time
            for attempt in range(3):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "FrenzAI/1.0 (audiobook narrator collection)"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        with open(str(mp3_path), "wb") as f:
                            f.write(resp.read())
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(3 + attempt * 2)
                    else:
                        raise e

            # Pick audio from the MIDDLE of the chapter (not intro)
            audio = AudioSegment.from_mp3(str(mp3_path))
            # Go to 40% into the chapter for clean narration (no intro music/credits)
            mid_point = int(len(audio) * 0.4)
            start_ms = mid_point
            end_ms = min(mid_point + 22000, len(audio))
            trimmed = audio[start_ms:end_ms]
            trimmed.export(str(wav_path), format="wav")
            mp3_path.unlink(missing_ok=True)

            # Add delay between downloads to avoid rate limiting
            time.sleep(2)

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
                    language=lang,
                    tags=tags,
                    notes=f"LibriVox narrator ({gender}). Source: archive.org/download/{archive_id}",
                    embedding_path=str(emb_path),
                    sample_path=str(wav_path),
                    quality_score=3.5,
                )
                session.add(voice)
                await session.commit()
                break

            created += 1
            print("OK")

        except Exception as e:
            failed += 1
            mp3_path.unlink(missing_ok=True)
            wav_path.unlink(missing_ok=True)
            print(f"FAILED: {e}")

    print(f"\nDone! Created: {created}, Failed: {failed}, Skipped: {skipped}")
    print(f"Total narrators in catalog: {len(REAL_NARRATORS)}")


if __name__ == "__main__":
    asyncio.run(main())

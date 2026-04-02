"""Seed 55 narrator voices as Kokoro blends into the FrenzAI database."""
import asyncio
import os
import sys
import uuid

# Fix paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = os.path.join(
    sys.prefix, "Lib", "site-packages", "espeakng_loader", "espeak-ng.dll"
)
os.environ["ESPEAK_DATA_PATH"] = os.path.join(
    sys.prefix, "Lib", "site-packages", "espeakng_loader", "espeak-ng-data"
)

NARRATORS = [
    # (name, language, gender, tags, [(voice_code, weight), ...])
    # American English Female (6)
    ("Emma Clarke", "en", "female", ["american", "narrator", "warm"], [("af_heart", 0.8), ("af_bella", 0.2)]),
    ("Sarah Mitchell", "en", "female", ["american", "narrator", "clear"], [("af_sarah", 0.9), ("af_nova", 0.1)]),
    ("Grace Anderson", "en", "female", ["american", "narrator", "expressive"], [("af_nova", 0.7), ("af_jessica", 0.3)]),
    ("Rachel Green", "en", "female", ["american", "narrator", "refined"], [("af_kore", 0.6), ("af_heart", 0.4)]),
    ("Claire Davis", "en", "female", ["american", "narrator", "composed"], [("af_alloy", 0.7), ("af_sky", 0.3)]),
    ("Maya Johnson", "en", "female", ["american", "narrator", "energetic"], [("af_jessica", 0.6), ("af_nova", 0.4)]),
    # American English Male (6)
    ("James Wilson", "en", "male", ["american", "narrator", "deep"], [("am_adam", 0.7), ("am_onyx", 0.3)]),
    ("Robert Parker", "en", "male", ["american", "narrator", "authoritative"], [("am_eric", 0.6), ("am_michael", 0.4)]),
    ("Thomas Blake", "en", "male", ["american", "narrator", "dramatic"], [("am_fenrir", 0.7), ("am_echo", 0.3)]),
    ("David Sterling", "en", "male", ["american", "narrator", "warm"], [("am_liam", 0.6), ("am_adam", 0.4)]),
    ("Michael Brooks", "en", "male", ["american", "narrator", "storyteller"], [("am_puck", 0.5), ("am_michael", 0.5)]),
    ("William Hart", "en", "male", ["american", "narrator", "adventurous"], [("am_echo", 0.7), ("am_fenrir", 0.3)]),
    # British English Female (4)
    ("Victoria Hughes", "en-gb", "female", ["british", "narrator", "elegant"], [("bf_emma", 0.6), ("bf_lily", 0.4)]),
    ("Charlotte Webb", "en-gb", "female", ["british", "narrator", "intense"], [("bf_isabella", 0.7), ("bf_alice", 0.3)]),
    ("Elizabeth May", "en-gb", "female", ["british", "narrator", "scholarly"], [("bf_alice", 0.5), ("bf_emma", 0.5)]),
    ("Diana Scott", "en-gb", "female", ["british", "narrator", "gentle"], [("bf_lily", 0.8), ("bf_isabella", 0.2)]),
    # British English Male (4)
    ("Arthur Pemberton", "en-gb", "male", ["british", "narrator", "classic"], [("bm_george", 0.6), ("bm_daniel", 0.4)]),
    ("George Whitfield", "en-gb", "male", ["british", "narrator", "precise"], [("bm_fable", 0.7), ("bm_lewis", 0.3)]),
    ("Henry Langford", "en-gb", "male", ["british", "narrator", "gothic"], [("bm_lewis", 0.6), ("bm_george", 0.4)]),
    ("Edward Thornton", "en-gb", "male", ["british", "narrator", "thoughtful"], [("bm_daniel", 0.5), ("bm_fable", 0.5)]),
    # German (6)
    ("Lena Fischer", "de", "female", ["german", "narrator"], [("af_heart", 0.5), ("af_bella", 0.5)]),
    ("Klara Schneider", "de", "female", ["german", "narrator"], [("af_nova", 0.6), ("af_kore", 0.4)]),
    ("Ingrid Hartmann", "de", "female", ["german", "narrator"], [("af_sarah", 0.7), ("af_alloy", 0.3)]),
    ("Hans Mueller", "de", "male", ["german", "narrator"], [("am_adam", 0.6), ("am_eric", 0.4)]),
    ("Friedrich Weber", "de", "male", ["german", "narrator"], [("am_michael", 0.5), ("am_fenrir", 0.5)]),
    ("Otto Braun", "de", "male", ["german", "narrator"], [("am_onyx", 0.7), ("am_liam", 0.3)]),
    # French (6)
    ("Marie Dupont", "fr", "female", ["french", "narrator"], [("ff_siwis", 0.9), ("af_heart", 0.1)]),
    ("Sophie Laurent", "fr", "female", ["french", "narrator"], [("ff_siwis", 0.7), ("af_bella", 0.3)]),
    ("Isabelle Roux", "fr", "female", ["french", "narrator"], [("ff_siwis", 0.6), ("af_nova", 0.4)]),
    ("Pierre Martin", "fr", "male", ["french", "narrator"], [("am_adam", 0.5), ("am_eric", 0.5)]),
    ("Jean Moreau", "fr", "male", ["french", "narrator"], [("am_michael", 0.6), ("am_liam", 0.4)]),
    ("Antoine Leroy", "fr", "male", ["french", "narrator"], [("am_fenrir", 0.5), ("am_onyx", 0.5)]),
    # Spanish (6)
    ("Carmen Ruiz", "es", "female", ["spanish", "narrator"], [("ef_dora", 0.9), ("af_heart", 0.1)]),
    ("Elena Morales", "es", "female", ["spanish", "narrator"], [("ef_dora", 0.7), ("af_bella", 0.3)]),
    ("Isabel Santos", "es", "female", ["spanish", "narrator"], [("ef_dora", 0.6), ("af_nova", 0.4)]),
    ("Alejandro Vega", "es", "male", ["spanish", "narrator"], [("em_alex", 0.8), ("am_adam", 0.2)]),
    ("Carlos Mendoza", "es", "male", ["spanish", "narrator"], [("em_alex", 0.5), ("am_eric", 0.5)]),
    ("Miguel Torres", "es", "male", ["spanish", "narrator"], [("em_santa", 0.6), ("am_michael", 0.4)]),
    # Italian (4)
    ("Giulia Romano", "it", "female", ["italian", "narrator"], [("if_sara", 0.9), ("af_heart", 0.1)]),
    ("Francesca Bianchi", "it", "female", ["italian", "narrator"], [("if_sara", 0.7), ("af_bella", 0.3)]),
    ("Marco Rossi", "it", "male", ["italian", "narrator"], [("im_nicola", 0.8), ("am_adam", 0.2)]),
    ("Alessandro Conti", "it", "male", ["italian", "narrator"], [("im_nicola", 0.6), ("am_eric", 0.4)]),
    # Nigerian English (4)
    ("Adaeze Okafor", "en", "female", ["nigerian", "narrator", "warm"], [("af_heart", 0.4), ("af_nicole", 0.3), ("af_river", 0.3)]),
    ("Ngozi Eze", "en", "female", ["nigerian", "narrator", "expressive"], [("af_nova", 0.4), ("af_jessica", 0.3), ("af_sky", 0.3)]),
    ("Chidi Nwosu", "en", "male", ["nigerian", "narrator", "commanding"], [("am_onyx", 0.4), ("am_adam", 0.3), ("am_eric", 0.3)]),
    ("Emeka Obi", "en", "male", ["nigerian", "narrator", "rich"], [("am_michael", 0.4), ("am_fenrir", 0.3), ("am_liam", 0.3)]),
    # Portuguese (3)
    ("Ana Silva", "pt", "female", ["portuguese", "narrator"], [("pf_dora", 0.9), ("af_heart", 0.1)]),
    ("Carlos Ferreira", "pt", "male", ["portuguese", "narrator"], [("pm_alex", 0.8), ("am_adam", 0.2)]),
    ("Lucia Santos", "pt", "female", ["portuguese", "narrator"], [("pf_dora", 0.7), ("af_bella", 0.3)]),
    # Hindi (4)
    ("Priya Sharma", "hi", "female", ["hindi", "narrator"], [("hf_alpha", 0.7), ("hf_beta", 0.3)]),
    ("Ananya Patel", "hi", "female", ["hindi", "narrator"], [("hf_beta", 0.8), ("hf_alpha", 0.2)]),
    ("Rajesh Kumar", "hi", "male", ["hindi", "narrator"], [("hm_omega", 0.6), ("hm_psi", 0.4)]),
    ("Vikram Singh", "hi", "male", ["hindi", "narrator"], [("hm_psi", 0.7), ("hm_omega", 0.3)]),
    # Japanese (3)
    ("Sakura Yamamoto", "ja", "female", ["japanese", "narrator"], [("jf_nezumi", 0.6), ("jf_tebukuro", 0.4)]),
    ("Haruki Mori", "ja", "female", ["japanese", "narrator"], [("jf_alpha", 0.5), ("jf_gongitsune", 0.5)]),
    ("Kenji Sato", "ja", "male", ["japanese", "narrator"], [("jm_kumo", 1.0)]),
]


async def main():
    import torch
    import numpy as np
    from app.config import settings
    from app.db.database import get_session
    from app.db.models import Voice
    from app.db.seed import create_tables
    from sqlalchemy import select
    from kokoro import KPipeline

    await create_tables()

    # Check existing
    async for session in get_session():
        result = await session.execute(select(Voice.name))
        existing = {r[0] for r in result.fetchall()}
        break

    # Pipeline cache per language
    pipelines = {}
    created = 0
    skipped = 0

    for name, lang, gender, tags, blend_spec in NARRATORS:
        if name in existing:
            skipped += 1
            print(f"  [{skipped + created}/{len(NARRATORS)}] Skip: {name} (exists)")
            continue

        # Get or create pipeline for the voice language
        first_code = blend_spec[0][0]
        lang_code = first_code[0]  # a, b, j, z, e, f, h, i, p
        if lang_code not in pipelines:
            pipelines[lang_code] = KPipeline(lang_code=lang_code)
        pipeline = pipelines[lang_code]

        # Blend voices
        voice_tensor = None
        for code, weight in blend_spec:
            code_lang = code[0]
            if code_lang not in pipelines:
                pipelines[code_lang] = KPipeline(lang_code=code_lang)
            t = pipelines[code_lang].load_voice(code)
            if voice_tensor is None:
                voice_tensor = weight * t
            else:
                voice_tensor = voice_tensor + weight * t

        # Save .pt file
        voice_id = str(uuid.uuid4())
        pt_path = settings.embeddings_dir / f"{voice_id}.pt"
        torch.save(voice_tensor, str(pt_path))

        # Save compat .npy
        npy_path = settings.embeddings_dir / f"{voice_id}.npy"
        compat = voice_tensor[0, 0, :].numpy().astype(np.float32)
        np.save(str(npy_path), compat)

        # Build blend description
        blend_desc = " + ".join(f"{c}({w:.0%})" for c, w in blend_spec)

        # Insert into DB
        async for session in get_session():
            voice = Voice(
                id=voice_id,
                name=name,
                engine="kokoro",
                language=lang,
                tags=tags,
                notes=f"Narrator blend ({gender}): {blend_desc}",
                embedding_path=str(pt_path),
                quality_score=4.0,
            )
            session.add(voice)
            await session.commit()
            break

        created += 1
        print(f"  [{skipped + created}/{len(NARRATORS)}] Created: {name} ({lang}, {gender})")

    print(f"\nDone! Created {created}, skipped {skipped}")
    print(f"Total narrator voices: {created + skipped}")


if __name__ == "__main__":
    asyncio.run(main())

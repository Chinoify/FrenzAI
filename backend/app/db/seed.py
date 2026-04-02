import sqlite3

from app.db.database import Base, engine
from app.config import settings


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Auto-migrate: add any missing columns to existing tables
    _migrate_missing_columns()


def _migrate_missing_columns():
    """Add missing columns to existing SQLite tables for seamless upgrades."""
    db_path = settings.data_dir / "voiceforge.db"
    if not db_path.exists():
        return

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Define expected columns for each table
        migrations = {
            "projects": {
                "source_type": 'TEXT DEFAULT "text"',
                "source_filename": "TEXT",
                "default_voice_id": "TEXT",
                "default_model": 'TEXT DEFAULT "kokoro"',
                "total_duration": "REAL",
                "status": 'TEXT DEFAULT "draft"',
            },
            "chapters": {
                "voice_id": "TEXT",
                "model": "TEXT",
            },
        }

        for table, columns in migrations.items():
            cursor.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cursor.fetchall()}
            for col, typedef in columns.items():
                if col not in existing:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")

        conn.commit()
        conn.close()
    except Exception:
        pass  # Don't crash on migration errors

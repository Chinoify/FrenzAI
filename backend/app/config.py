from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "FrenzAI"
    version: str = "1.0.0"
    host: str = "127.0.0.1"
    port: int = 8111
    debug: bool = False

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = base_dir / "data"
    models_dir: Path = base_dir / "backend" / "models"
    voices_dir: Path = data_dir / "voices"
    embeddings_dir: Path = voices_dir / "embeddings"
    samples_dir: Path = voices_dir / "samples"
    projects_dir: Path = data_dir / "projects"
    exports_dir: Path = data_dir / "exports"
    temp_dir: Path = data_dir / "temp"
    db_path: Path = data_dir / "voiceforge.db"

    # Audio defaults
    default_sample_rate: int = 48000
    max_text_length: int = 50000
    temp_cleanup_hours: int = 2

    # Device
    device: str = "auto"  # "auto", "cuda", "cpu"

    class Config:
        env_prefix = "VOICEFORGE_"


settings = Settings()

# Ensure directories exist
for d in [
    settings.data_dir,
    settings.models_dir,
    settings.voices_dir,
    settings.embeddings_dir,
    settings.samples_dir,
    settings.projects_dir,
    settings.exports_dir,
    settings.temp_dir,
]:
    d.mkdir(parents=True, exist_ok=True)

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Health ---
class GPUInfo(BaseModel):
    available: bool
    name: Optional[str] = None
    vram_total_mb: Optional[int] = None
    vram_used_mb: Optional[int] = None
    vram_free_mb: Optional[int] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    gpu: GPUInfo
    active_model: Optional[str] = None
    voices_count: int = 0
    device: str = "cpu"


# --- TTS ---
class TTSGenerateRequest(BaseModel):
    text: str = Field(..., max_length=50000)
    model: str = "builtin"
    voice_id: Optional[str] = None
    language: str = "en"
    speed: float = Field(1.0, ge=0.25, le=4.0)
    stability: float = Field(0.7, ge=0.0, le=1.0)
    clarity: float = Field(0.8, ge=0.0, le=1.0)
    steps: int = Field(4, ge=1, le=50)


class TTSGenerateResponse(BaseModel):
    audio_url: str
    duration: float
    generation_time: float


class TTSBatchRequest(BaseModel):
    paragraphs: list[str]
    model: str = "builtin"
    voice_id: Optional[str] = None
    language: str = "en"
    speed: float = 1.0
    stability: float = 0.7
    clarity: float = 0.8
    steps: int = 4


# --- Voice ---
class VoiceCreate(BaseModel):
    name: str
    engine: str = "kokoro"
    language: str = "en"
    tags: list[str] = []
    notes: str = ""


class VoiceUpdate(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    is_favorite: Optional[bool] = None


class VoiceResponse(BaseModel):
    id: str
    name: str
    engine: str
    language: str
    tags: list[str]
    notes: str
    quality_score: float
    use_count: int
    is_favorite: bool
    sample_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Project ---
class ProjectCreate(BaseModel):
    name: str
    text: str
    voice_id: Optional[str] = None
    model: Optional[str] = None
    language: str = "en"
    params: dict = {}


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    text: Optional[str] = None
    voice_id: Optional[str] = None
    model: Optional[str] = None
    default_model: Optional[str] = None
    language: Optional[str] = None
    params: Optional[dict] = None


class SegmentInfo(BaseModel):
    index: int
    text: str
    audio_path: Optional[str] = None
    duration: Optional[float] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    text: str
    voice_id: Optional[str]
    model: Optional[str]
    language: str
    params: dict
    segments: list[SegmentInfo]
    merged_audio_path: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- History ---
class HistoryResponse(BaseModel):
    id: int
    text_preview: Optional[str]
    voice_name: Optional[str]
    model: Optional[str]
    audio_url: Optional[str]
    duration_seconds: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Models ---
class ModelInfo(BaseModel):
    name: str
    display_name: str
    description: str
    languages: list[str]
    vram_required_mb: int
    model_size_mb: int
    license: str
    is_downloaded: bool
    is_loaded: bool


class ModelListResponse(BaseModel):
    models: list[ModelInfo]
    active_model: Optional[str] = None


# --- Audio ---
# --- Chapter / Audiobook ---
class ChapterResponse(BaseModel):
    id: str
    index: int
    title: str
    text: str
    voice_id: Optional[str] = None
    model: Optional[str] = None
    status: str = "pending"
    audio_url: Optional[str] = None
    duration: Optional[float] = None

    class Config:
        from_attributes = True


class ChapterCreate(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    index: Optional[int] = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    voice_id: Optional[str] = None
    model: Optional[str] = None


class ProjectDetailResponse(BaseModel):
    id: str
    name: str
    source_type: Optional[str] = "text"
    source_filename: Optional[str] = None
    default_voice_id: Optional[str] = None
    default_model: Optional[str] = "kokoro"
    total_duration: Optional[float] = None
    status: str = "draft"
    language: str = "en"
    chapters: list[ChapterResponse] = []
    merged_audio_path: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GenerateChaptersRequest(BaseModel):
    chapter_ids: Optional[list[str]] = None  # None = all chapters
    voice_id: Optional[str] = None
    model: Optional[str] = None
    language: str = "en"
    speed: float = 1.0


class MergeExportRequest(BaseModel):
    format: str = "wav"  # wav, mp3, mp3-acx, lpf
    gap_seconds: float = 2.0
    acx_compliant: bool = False


# --- Audio ---
class AudioExportRequest(BaseModel):
    audio_path: str
    format: str = "wav"  # wav, mp3, flac
    sample_rate: int = 48000
    bitrate: str = "320k"


class AudioMergeRequest(BaseModel):
    audio_paths: list[str]
    output_format: str = "wav"
    crossfade_ms: int = 0

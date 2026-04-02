from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import JSON

from app.db.database import Base


class Voice(Base):
    __tablename__ = "voices"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    engine = Column(String, nullable=False)
    language = Column(String, default="en")
    tags = Column(JSON, default=list)
    notes = Column(Text, default="")
    embedding_path = Column(String)
    sample_path = Column(String)
    quality_score = Column(Float, default=0.0)
    use_count = Column(Integer, default=0)
    is_favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    text = Column(Text, nullable=False, default="")
    voice_id = Column(String, ForeignKey("voices.id", ondelete="SET NULL"), nullable=True)
    model = Column(String)
    language = Column(String, default="en")
    params = Column(JSON, default=dict)
    segments = Column(JSON, default=list)
    merged_audio_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    # New audiobook fields
    source_type = Column(String, default="text")  # text, epub, pdf, txt, docx
    source_filename = Column(String, nullable=True)
    default_voice_id = Column(String, ForeignKey("voices.id", ondelete="SET NULL"), nullable=True)
    default_model = Column(String, default="kokoro")
    total_duration = Column(Float, nullable=True)
    status = Column(String, default="draft")  # draft, generating, completed, error


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    index = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    voice_id = Column(String, ForeignKey("voices.id", ondelete="SET NULL"), nullable=True)
    model = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, generating, completed, error
    audio_path = Column(String, nullable=True)
    duration = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GenerationHistory(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text_preview = Column(String)
    voice_name = Column(String)
    model = Column(String)
    audio_path = Column(String)
    duration_seconds = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

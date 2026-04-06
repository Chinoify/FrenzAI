import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_session
from app.db.models import Chapter, Project, Voice
from app.schemas import (
    ChapterCreate,
    ChapterResponse,
    ChapterUpdate,
    GenerateChaptersRequest,
    MergeExportRequest,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectResponse,
    ProjectUpdate,
    SegmentInfo,
)
from app.services.document_parser import parse_file, parse_text

router = APIRouter(prefix="/api/projects", tags=["projects"])


# --- Kokoro voices list (MUST be before /{project_id} to avoid conflict) ---
@router.get("/kokoro-voices")
async def get_kokoro_voices():
    """Return all available Kokoro TTS voices."""
    try:
        from app.engines.kokoro_engine import ALL_VOICES, VOICE_DISPLAY_NAMES
    except ImportError:
        return {"voices": []}

    voices = []
    for code in ALL_VOICES:
        display_name = VOICE_DISPLAY_NAMES.get(code, code)
        prefix = code[0]
        lang_map = {
            "a": "en", "b": "en-gb", "j": "ja", "z": "zh",
            "e": "es", "f": "fr", "h": "hi", "i": "it", "p": "pt",
        }
        lang = lang_map.get(prefix, "en")
        gender = "female" if code[1] == "f" else "male"
        voices.append({
            "code": code,
            "name": display_name,
            "language": lang,
            "gender": gender,
        })
    return {"voices": voices}


# --- Import from URL (Google Docs, web pages) ---
@router.post("/import-url", response_model=ProjectDetailResponse)
async def import_from_url(
    req: dict,
    session: AsyncSession = Depends(get_session),
):
    """Import text from a Google Docs link or web URL."""
    import re
    import urllib.request
    from bs4 import BeautifulSoup

    url = req.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Convert Google Docs edit URL to export URL
    gdocs_match = re.match(r"https://docs\.google\.com/document/d/([^/]+)", url)
    if gdocs_match:
        doc_id = gdocs_match.group(1)
        url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

    try:
        req_obj = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_obj, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()

            if "text/plain" in content_type:
                text = raw.decode("utf-8", errors="replace")
            else:
                # HTML — extract text
                soup = BeautifulSoup(raw, "html.parser")
                # Remove scripts and styles
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")

    text = text.strip()
    if not text or len(text) < 20:
        raise HTTPException(status_code=400, detail="No meaningful text found at URL")

    # Parse chapters
    parsed_chapters = parse_text(text)

    # Generate name from URL or first line
    name = text.split("\n")[0][:80].strip() or "Imported Document"
    if gdocs_match:
        name = f"Google Doc: {name}"

    project = Project(
        id=str(uuid.uuid4()),
        name=name,
        text=text[:500],
        source_type="url",
        source_filename=url[:200],
        default_model="kokoro",
        language="en",
        status="draft",
    )
    session.add(project)

    db_chapters = []
    for i, ch in enumerate(parsed_chapters):
        chapter = Chapter(
            id=str(uuid.uuid4()),
            project_id=project.id,
            index=i,
            title=ch.title,
            text=ch.text,
        )
        session.add(chapter)
        db_chapters.append(chapter)

    await session.commit()
    await session.refresh(project)
    return _detail_response(project, db_chapters)


# --- List Projects ---
@router.get("", response_model=list[ProjectDetailResponse])
async def list_projects(session: AsyncSession = Depends(get_session)):
    query = select(Project).order_by(Project.created_at.desc())
    result = await session.execute(query)
    projects = result.scalars().all()
    responses = []
    for p in projects:
        chapters = await _get_chapters(session, p.id)
        responses.append(_detail_response(p, chapters))
    return responses


# --- Upload Book ---
@router.post("/upload", response_model=ProjectDetailResponse)
async def upload_book(
    file: UploadFile = File(...),
    name: str = Form(""),
    default_model: str = Form("kokoro"),
    language: str = Form("en"),
    session: AsyncSession = Depends(get_session),
):
    # Save uploaded file
    upload_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "txt"
    upload_path = settings.temp_dir / f"upload_{upload_id}.{ext}"

    try:
        content = await file.read()
        with open(upload_path, "wb") as f:
            f.write(content)
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    # Parse into chapters
    try:
        parsed_chapters = parse_file(upload_path)
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    if not parsed_chapters:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="No content found in file")

    # Create project
    project_name = name or (file.filename or "Untitled Book").rsplit(".", 1)[0]
    all_text = "\n\n".join(ch.text for ch in parsed_chapters)

    project = Project(
        id=str(uuid.uuid4()),
        name=project_name,
        text=all_text[:500],  # Preview only
        source_type=ext.lower(),
        source_filename=file.filename,
        default_model=default_model,
        language=language,
        status="draft",
    )
    session.add(project)

    # Create chapters
    db_chapters = []
    for i, ch in enumerate(parsed_chapters):
        chapter = Chapter(
            id=str(uuid.uuid4()),
            project_id=project.id,
            index=i,
            title=ch.title,
            text=ch.text,
        )
        session.add(chapter)
        db_chapters.append(chapter)

    await session.commit()
    await session.refresh(project)

    # Clean up upload
    upload_path.unlink(missing_ok=True)

    return _detail_response(project, db_chapters)


# --- Create from text ---
@router.post("", response_model=ProjectDetailResponse)
async def create_project(req: ProjectCreate, session: AsyncSession = Depends(get_session)):
    # Parse text into chapters
    parsed_chapters = parse_text(req.text)

    project = Project(
        id=str(uuid.uuid4()),
        name=req.name,
        text=req.text[:500],
        source_type="text",
        default_model=req.model or "kokoro",
        language=req.language,
        status="draft",
    )
    session.add(project)

    db_chapters = []
    for i, ch in enumerate(parsed_chapters):
        chapter = Chapter(
            id=str(uuid.uuid4()),
            project_id=project.id,
            index=i,
            title=ch.title,
            text=ch.text,
        )
        session.add(chapter)
        db_chapters.append(chapter)

    await session.commit()
    await session.refresh(project)
    return _detail_response(project, db_chapters)


# --- Get project detail ---
@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: str, session: AsyncSession = Depends(get_session)):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    chapters = await _get_chapters(session, project_id)
    return _detail_response(project, chapters)


# --- Update project ---
@router.patch("/{project_id}", response_model=ProjectDetailResponse)
async def update_project(
    project_id: str,
    update: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    chapters = await _get_chapters(session, project_id)
    return _detail_response(project, chapters)


# --- Delete project ---
@router.delete("/{project_id}")
async def delete_project(project_id: str, session: AsyncSession = Depends(get_session)):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    # Delete chapter audio
    chapters = await _get_chapters(session, project_id)
    for ch in chapters:
        if ch.audio_path:
            Path(ch.audio_path).unlink(missing_ok=True)
        await session.delete(ch)
    if project.merged_audio_path:
        Path(project.merged_audio_path).unlink(missing_ok=True)
    await session.delete(project)
    await session.commit()
    return {"status": "deleted"}


# --- List chapters ---
@router.get("/{project_id}/chapters", response_model=list[ChapterResponse])
async def list_chapters(project_id: str, session: AsyncSession = Depends(get_session)):
    chapters = await _get_chapters(session, project_id)
    return [_chapter_response(ch) for ch in chapters]


# --- Create chapter (manual) ---
@router.post("/{project_id}/chapters", response_model=ChapterResponse)
async def create_chapter(
    project_id: str,
    req: ChapterCreate,
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapters = await _get_chapters(session, project_id)
    # Insert at specified index or at end
    insert_index = req.index if req.index is not None else len(chapters)

    # Shift existing chapters
    for ch in chapters:
        if ch.index >= insert_index:
            ch.index += 1

    chapter = Chapter(
        id=str(uuid.uuid4()),
        project_id=project_id,
        index=insert_index,
        title=req.title or f"Chapter {insert_index + 1}",
        text=req.text or "",
    )
    session.add(chapter)
    await session.commit()
    await session.refresh(chapter)
    return _chapter_response(chapter)


# --- Update chapter ---
@router.patch("/{project_id}/chapters/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    project_id: str,
    chapter_id: str,
    update: ChapterUpdate,
    session: AsyncSession = Depends(get_session),
):
    chapter = await session.get(Chapter, chapter_id)
    if not chapter or chapter.project_id != project_id:
        raise HTTPException(status_code=404, detail="Chapter not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        # Treat empty string as None for voice_id and model
        if field in ("voice_id", "model") and value == "":
            value = None
        setattr(chapter, field, value)
    # If text changed, mark as needing regeneration but keep existing audio
    if update.text is not None and chapter.audio_path:
        chapter.status = "edited"
    await session.commit()
    await session.refresh(chapter)
    return _chapter_response(chapter)


# --- Delete chapter ---
@router.delete("/{project_id}/chapters/{chapter_id}")
async def delete_chapter(
    project_id: str,
    chapter_id: str,
    session: AsyncSession = Depends(get_session),
):
    chapter = await session.get(Chapter, chapter_id)
    if not chapter or chapter.project_id != project_id:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if chapter.audio_path:
        Path(chapter.audio_path).unlink(missing_ok=True)

    deleted_index = chapter.index
    await session.delete(chapter)

    # Re-index remaining chapters
    remaining = await _get_chapters(session, project_id)
    for ch in remaining:
        if ch.index > deleted_index:
            ch.index -= 1

    await session.commit()
    return {"status": "deleted"}


# --- Reorder chapters ---
@router.post("/{project_id}/chapters/reorder")
async def reorder_chapters(
    project_id: str,
    order: list[str],  # list of chapter IDs in new order
    session: AsyncSession = Depends(get_session),
):
    chapters = await _get_chapters(session, project_id)
    chapter_map = {ch.id: ch for ch in chapters}

    for i, ch_id in enumerate(order):
        if ch_id in chapter_map:
            chapter_map[ch_id].index = i

    await session.commit()
    return {"status": "reordered"}


# --- Generate single chapter ---
@router.post("/{project_id}/chapters/{chapter_id}/generate", response_model=ChapterResponse)
async def generate_chapter(
    project_id: str,
    chapter_id: str,
    session: AsyncSession = Depends(get_session),
):
    from app.services.audiobook_service import generate_chapter_audio
    from app.services.voice_service import get_voice_embedding

    chapter = await session.get(Chapter, chapter_id)
    if not chapter or chapter.project_id != project_id:
        raise HTTPException(status_code=404, detail="Chapter not found")

    project = await session.get(Project, project_id)
    raw_model = chapter.model or project.default_model or "kokoro"

    # Parse kokoro:voice_code format
    kokoro_voice = None
    engine_name = raw_model
    if raw_model.startswith("kokoro:"):
        engine_name = "kokoro"
        kokoro_voice = raw_model.split(":", 1)[1]

    voice_id = chapter.voice_id or project.default_voice_id

    # Load voice
    voice_embedding = None
    sample_path = None
    embedding_path = None
    if voice_id:
        voice = await session.get(Voice, voice_id)
        if voice:
            voice_embedding = await get_voice_embedding(voice)
            sample_path = voice.sample_path
            embedding_path = voice.embedding_path
            # Use the voice's engine for cloned voices (not the project default)
            if not kokoro_voice and voice.engine:
                engine_name = voice.engine

    chapter.status = "generating"
    await session.commit()

    try:
        audio_path, duration = await generate_chapter_audio(
            text=chapter.text,
            engine_name=engine_name,
            voice_embedding=voice_embedding,
            sample_path=sample_path,
            language=project.language,
            kokoro_voice=kokoro_voice,
            embedding_path=embedding_path,
        )
        chapter.audio_path = audio_path
        chapter.duration = duration
        chapter.status = "completed"
    except Exception as e:
        chapter.status = "error"
        await session.commit()
        raise HTTPException(status_code=500, detail=str(e))

    await session.commit()
    await session.refresh(chapter)
    return _chapter_response(chapter)


# --- Generate all chapters (SSE streaming) ---
@router.post("/{project_id}/generate")
async def generate_all_chapters(
    project_id: str,
    req: GenerateChaptersRequest,
    session: AsyncSession = Depends(get_session),
):
    from app.services.audiobook_service import generate_chapter_audio
    from app.services.voice_service import get_voice_embedding

    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapters = await _get_chapters(session, project_id)
    if req.chapter_ids:
        chapters = [ch for ch in chapters if ch.id in req.chapter_ids]

    raw_model = req.model or project.default_model or "kokoro"
    # Parse kokoro:voice_code format at project level
    project_kokoro_voice = None
    engine_name = raw_model
    if raw_model.startswith("kokoro:"):
        engine_name = "kokoro"
        project_kokoro_voice = raw_model.split(":", 1)[1]

    # Load voice
    voice_embedding = None
    sample_path = None
    voice_id = req.voice_id or project.default_voice_id
    if voice_id:
        voice = await session.get(Voice, voice_id)
        if voice:
            voice_embedding = await get_voice_embedding(voice)
            sample_path = voice.sample_path
            # Use the voice's engine for cloned voices
            if not project_kokoro_voice and voice.engine:
                engine_name = voice.engine

    # Run generation as background task so it continues even if user leaves page
    import asyncio

    async def _generate_bg():
        from app.db.database import async_session
        async with async_session() as bg_session:
            bg_project = await bg_session.get(Project, project_id)
            bg_chapters = await _get_chapters(bg_session, project_id)
            if req.chapter_ids:
                bg_chapters = [ch for ch in bg_chapters if ch.id in req.chapter_ids]

            bg_project.status = "generating"
            await bg_session.commit()

            for i, chapter in enumerate(bg_chapters):
                ch_voice_embedding = voice_embedding
                ch_sample_path = sample_path
                ch_kokoro_voice = project_kokoro_voice
                ch_engine = engine_name

                if chapter.voice_id:
                    ch_voice = await bg_session.get(Voice, chapter.voice_id)
                    if ch_voice:
                        ch_voice_embedding = await get_voice_embedding(ch_voice)
                        ch_sample_path = ch_voice.sample_path
                        if ch_voice.engine:
                            ch_engine = ch_voice.engine
                            ch_kokoro_voice = None

                ch_raw_model = chapter.model or raw_model
                if not chapter.voice_id:
                    ch_engine = ch_raw_model
                if ch_raw_model.startswith("kokoro:"):
                    ch_engine = "kokoro"
                    ch_kokoro_voice = ch_raw_model.split(":", 1)[1]

                try:
                    audio_path, duration = await generate_chapter_audio(
                        text=chapter.text,
                        engine_name=ch_engine,
                        voice_embedding=ch_voice_embedding,
                        sample_path=ch_sample_path,
                        language=req.language,
                        speed=req.speed,
                        kokoro_voice=ch_kokoro_voice,
                    )
                    chapter.audio_path = audio_path
                    chapter.duration = duration
                    chapter.status = "completed"
                except Exception as e:
                    chapter.status = "error"
                    print(f"[Audiobook] Chapter {i+1} error: {e}", flush=True)
                await bg_session.commit()
                print(f"[Audiobook] Chapter {i+1}/{len(bg_chapters)}: {chapter.title} - {chapter.status}", flush=True)

            bg_project.status = "completed"
            bg_project.total_duration = round(sum(ch.duration or 0 for ch in bg_chapters), 2)
            await bg_session.commit()
            print(f"[Audiobook] Done! Total: {bg_project.total_duration}s", flush=True)

    asyncio.create_task(_generate_bg())

    async def progress_stream():
        # Send initial response then poll status
        total = len(chapters)
        yield f"data: {json.dumps({'chapter': 0, 'total': total, 'status': 'started'})}\n\n"

        for _ in range(total * 60):  # poll for up to 60s per chapter
            await asyncio.sleep(2)
            await session.refresh(project)
            completed = 0
            for ch in await _get_chapters(session, project_id):
                if ch.status in ("completed", "error"):
                    completed += 1
            yield f"data: {json.dumps({'chapter': completed, 'total': total, 'status': 'generating'})}\n\n"
            if completed >= total:
                break

        await session.refresh(project)
        yield f"data: {json.dumps({'status': 'completed', 'total_duration': project.total_duration or 0})}\n\n"

    return StreamingResponse(progress_stream(), media_type="text/event-stream")


# --- Merge & export ---
@router.post("/{project_id}/merge")
async def merge_and_export(
    project_id: str,
    req: MergeExportRequest,
    session: AsyncSession = Depends(get_session),
):
    from app.services.audiobook_service import merge_chapter_audio

    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapters = await _get_chapters(session, project_id)
    audio_paths = [ch.audio_path for ch in chapters if ch.audio_path and ch.status == "completed"]

    if not audio_paths:
        raise HTTPException(status_code=400, detail="No completed chapters to merge")

    merged_path = await merge_chapter_audio(
        audio_paths=audio_paths,
        output_format=req.format,
        gap_seconds=req.gap_seconds,
        acx_compliant=req.acx_compliant,
    )

    project.merged_audio_path = merged_path
    await session.commit()

    return {"status": "merged", "path": merged_path, "format": req.format}


# --- Export individual chapters as ACX MP3 ---
@router.post("/{project_id}/export-chapters")
async def export_chapters_acx(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Export each chapter as a separate ACX-compliant MP3 file."""
    from app.services.audiobook_service import export_chapter_acx

    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapters = await _get_chapters(session, project_id)
    completed = [ch for ch in chapters if ch.audio_path and ch.status == "completed"]

    if not completed:
        raise HTTPException(status_code=400, detail="No completed chapters to export")

    exported = []
    for ch in completed:
        try:
            path = await export_chapter_acx(ch.audio_path, ch.title)
            exported.append({
                "chapter_id": ch.id,
                "title": ch.title,
                "path": path,
                "url": f"/audio/exports/{Path(path).name}",
            })
        except Exception as e:
            exported.append({
                "chapter_id": ch.id,
                "title": ch.title,
                "error": str(e),
            })

    return {"status": "exported", "chapters": exported}


# --- Export chapters as ZIP with SSE progress ---
@router.post("/{project_id}/export-zip-progress")
async def export_chapters_zip_progress(
    project_id: str,
    req: dict = {},
    session: AsyncSession = Depends(get_session),
):
    """Stream export progress via SSE, then return download URL."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapters = await _get_chapters(session, project_id)
    completed = [ch for ch in chapters if ch.audio_path and ch.status in ("completed", "edited")]

    if not completed:
        raise HTTPException(status_code=400, detail="No completed chapters to export")

    fmt = req.get("format", "mp3")
    acx = fmt == "mp3-acx"

    zip_id = str(uuid.uuid4())[:8]
    safe_name = "".join(c for c in project.name if c.isalnum() or c in " _-").strip().replace(" ", "_") or "audiobook"
    zip_path = settings.exports_dir / f"{safe_name}_{zip_id}.zip"

    async def progress_stream():
        import zipfile
        from pydub import AudioSegment

        total = len(completed)

        yield f"data: {json.dumps({'step': 'start', 'total': total, 'message': 'Starting export...'})}\n\n"

        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for i, ch in enumerate(completed):
                pct = round(((i) / total) * 100)
                yield f"data: {json.dumps({'step': 'processing', 'current': i + 1, 'total': total, 'pct': pct, 'title': ch.title, 'message': f'Processing {ch.title}...'})}\n\n"

                src = Path(ch.audio_path)
                if not src.exists():
                    continue

                safe_title = "".join(c for c in ch.title if c.isalnum() or c in " _-").strip().replace(" ", "_")[:50] or f"chapter_{i+1}"
                chapter_filename = f"{i+1:02d}_{safe_title}"

                if fmt == "wav":
                    zf.write(str(src), f"{chapter_filename}.wav")
                else:
                    segment = AudioSegment.from_file(str(src))

                    if acx:
                        import numpy as np
                        from app.services.audio_processor import acx_normalize, resample

                        samples = np.array(segment.get_array_of_samples(), dtype=np.float32)
                        samples = samples / (2 ** (segment.sample_width * 8 - 1))
                        sr = segment.frame_rate
                        if sr != 44100:
                            samples = resample(samples, sr, 44100)
                        samples = acx_normalize(samples, 44100)
                        samples_int16 = (samples * 32767).clip(-32768, 32767).astype(np.int16)
                        segment = AudioSegment(
                            data=samples_int16.tobytes(), sample_width=2,
                            frame_rate=44100, channels=1,
                        )

                    tmp = settings.temp_dir / f"zip_ch_{zip_id}_{i}.mp3"
                    params = ["-ar", "44100", "-ac", "1"] if acx else []
                    segment.export(str(tmp), format="mp3", bitrate="192k", parameters=params)
                    zf.write(str(tmp), f"{chapter_filename}.mp3")
                    tmp.unlink(missing_ok=True)

        yield f"data: {json.dumps({'step': 'done', 'pct': 100, 'total': total, 'message': 'Export complete!', 'download_url': f'/api/projects/{project_id}/download-zip/{safe_name}_{zip_id}.zip'})}\n\n"

    return StreamingResponse(progress_stream(), media_type="text/event-stream")


# --- Download a zip file ---
@router.get("/{project_id}/download-zip/{filename}")
async def download_zip(project_id: str, filename: str):
    zip_path = settings.exports_dir / filename
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="ZIP file not found")
    safe_name = filename.rsplit("_", 1)[0] or "audiobook"
    return FileResponse(str(zip_path), filename=f"{safe_name}.zip", media_type="application/zip")


# --- Download export ---
@router.get("/{project_id}/export")
async def download_export(project_id: str, session: AsyncSession = Depends(get_session)):
    project = await session.get(Project, project_id)
    if not project or not project.merged_audio_path:
        raise HTTPException(status_code=404, detail="No exported file available")

    path = Path(project.merged_audio_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")

    filename = f"{project.name.replace(' ', '_')}{path.suffix}"
    return FileResponse(str(path), filename=filename, media_type="application/octet-stream")


# --- Helpers ---
async def _get_chapters(session: AsyncSession, project_id: str) -> list[Chapter]:
    result = await session.execute(
        select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.index)
    )
    return list(result.scalars().all())


def _chapter_response(ch: Chapter) -> ChapterResponse:
    audio_url = None
    if ch.audio_path:
        p = Path(ch.audio_path)
        audio_url = f"/audio/temp/{p.name}"
    return ChapterResponse(
        id=ch.id,
        index=ch.index,
        title=ch.title,
        text=ch.text,
        voice_id=ch.voice_id,
        model=ch.model,
        status=ch.status,
        audio_url=audio_url,
        duration=ch.duration,
    )


def _detail_response(p: Project, chapters: list[Chapter]) -> ProjectDetailResponse:
    merged_url = None
    if p.merged_audio_path and Path(p.merged_audio_path).exists():
        merged_url = f"/audio/exports/{Path(p.merged_audio_path).name}"
    return ProjectDetailResponse(
        id=p.id,
        name=p.name,
        source_type=getattr(p, "source_type", "text"),
        source_filename=getattr(p, "source_filename", None),
        default_voice_id=getattr(p, "default_voice_id", None),
        default_model=getattr(p, "default_model", "kokoro"),
        total_duration=getattr(p, "total_duration", None),
        status=getattr(p, "status", "draft"),
        language=p.language,
        chapters=[_chapter_response(ch) for ch in chapters],
        merged_audio_path=merged_url,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )

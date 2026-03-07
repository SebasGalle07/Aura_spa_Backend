from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import HTTPException, UploadFile

from app.core.config import settings


def _guess_ext(filename: str | None, content_type: str | None) -> str:
    if filename:
        ext = Path(filename).suffix.lower()
        if ext:
            return ext
    if content_type:
        mapping = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
        }
        return mapping.get(content_type.lower(), "")
    return ""


def _assert_image(file: UploadFile) -> None:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos de imagen")


def _save_local(file: UploadFile) -> str:
    media_dir = Path(settings.MEDIA_ROOT) / "branding"
    media_dir.mkdir(parents=True, exist_ok=True)

    ext = _guess_ext(file.filename, file.content_type)
    filename = f"branding_{uuid4().hex}{ext}"
    dest = media_dir / filename

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    return f"{settings.MEDIA_URL}/branding/{filename}"


def _save_gcs(file: UploadFile) -> str:
    from google.cloud import storage

    ext = _guess_ext(file.filename, file.content_type)
    object_name = f"{settings.STORAGE_PREFIX.strip('/')}/branding_{uuid4().hex}{ext}"

    client = storage.Client()
    bucket = client.bucket(settings.STORAGE_BUCKET)
    blob = bucket.blob(object_name)
    blob.cache_control = "public, max-age=3600"
    blob.upload_from_file(file.file, content_type=file.content_type)

    return f"https://storage.googleapis.com/{settings.STORAGE_BUCKET}/{object_name}"


def save_branding_image(file: UploadFile) -> str:
    _assert_image(file)
    if settings.STORAGE_BUCKET:
        return _save_gcs(file)
    return _save_local(file)

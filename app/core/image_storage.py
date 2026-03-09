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
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/svg+xml': '.svg',
        }
        return mapping.get(content_type.lower(), '')
    return ''


def _assert_image(file: UploadFile) -> None:
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='Solo se permiten archivos de imagen')


def _build_filename(stem: str, file: UploadFile) -> str:
    ext = _guess_ext(file.filename, file.content_type)
    return f'{stem}_{uuid4().hex}{ext}'


def _save_local(file: UploadFile, folder: str, stem: str) -> str:
    media_dir = Path(settings.MEDIA_ROOT) / folder
    media_dir.mkdir(parents=True, exist_ok=True)

    filename = _build_filename(stem, file)
    dest = media_dir / filename

    with dest.open('wb') as out:
        shutil.copyfileobj(file.file, out)

    return f'{settings.MEDIA_URL}/{folder}/{filename}'


def _save_gcs(file: UploadFile, folder: str, stem: str) -> str:
    from google.cloud import storage

    filename = _build_filename(stem, file)
    prefix = settings.STORAGE_PREFIX.strip('/')
    object_name = f'{prefix}/{folder}/{filename}' if prefix else f'{folder}/{filename}'

    client = storage.Client()
    bucket = client.bucket(settings.STORAGE_BUCKET)
    blob = bucket.blob(object_name)
    blob.cache_control = 'public, max-age=3600'
    blob.upload_from_file(file.file, content_type=file.content_type)

    return f'https://storage.googleapis.com/{settings.STORAGE_BUCKET}/{object_name}'


def save_public_image(file: UploadFile, folder: str, stem: str) -> str:
    _assert_image(file)
    if settings.STORAGE_BUCKET:
        return _save_gcs(file, folder, stem)
    return _save_local(file, folder, stem)


def _delete_local_by_url(file_url: str) -> None:
    prefix = f'{settings.MEDIA_URL}/'
    if not file_url.startswith(prefix):
        return
    rel_path = file_url[len(prefix) :]
    path = Path(settings.MEDIA_ROOT) / rel_path
    if path.exists() and path.is_file():
        path.unlink()


def _delete_gcs_by_url(file_url: str) -> None:
    if not settings.STORAGE_BUCKET:
        return
    base = f'https://storage.googleapis.com/{settings.STORAGE_BUCKET}/'
    if not file_url.startswith(base):
        return
    object_name = file_url[len(base) :]
    if not object_name:
        return

    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(settings.STORAGE_BUCKET)
    blob = bucket.blob(object_name)
    if blob.exists():
        blob.delete()


def delete_public_image_by_url(file_url: str | None) -> None:
    if not file_url:
        return
    if settings.STORAGE_BUCKET:
        _delete_gcs_by_url(file_url)
    else:
        _delete_local_by_url(file_url)


def save_branding_image(file: UploadFile) -> str:
    return save_public_image(file, folder='branding', stem='branding')

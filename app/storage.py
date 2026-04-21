from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import requests
from flask import current_app
from werkzeug.utils import secure_filename

from .utils import allowed_file, allowed_video_file, save_image, save_video


class StorageServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredImage:
    storage_key: str
    public_url: str


def _storage_base_url() -> str:
    base_url = (current_app.config.get("FILE_STORAGE_API_BASE_URL") or "").strip().rstrip("/")
    if not base_url:
        raise StorageServiceError("Recipe image storage is not configured. Please set FILE_STORAGE_API_BASE_URL.")
    return base_url


def _storage_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = (current_app.config.get("FILE_STORAGE_API_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _storage_timeout() -> float:
    return float(current_app.config.get("FILE_STORAGE_TIMEOUT_SECONDS", 10))


# Internal function to upload an image to the storage service, returning a StoredImage with the public URL and storage key
def _upload_image(file_storage, *, folder: str) -> StoredImage:
    if not file_storage or file_storage.filename == "":
        raise ValueError("Please choose an image to upload.")
    if not allowed_file(file_storage.filename):
        raise ValueError("Unsupported file type. Use png/jpg/jpeg/webp.")

    filename = secure_filename(file_storage.filename) or "recipe-image"
    file_storage.stream.seek(0)
    file_bytes = file_storage.stream.read()

    try:
        response = requests.post(
            f"{_storage_base_url()}/files",
            headers=_storage_headers(),
            data={"folder": folder},
            files={"file": (filename, file_bytes, file_storage.mimetype or "application/octet-stream")},
            timeout=_storage_timeout(),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise StorageServiceError("Could not upload the recipe image right now. Please try again.") from exc
    except ValueError as exc:
        raise StorageServiceError("Storage service returned invalid image data.") from exc

    storage_key = payload.get("file_id") or payload.get("id") or payload.get("storage_key") or payload.get("key")
    public_url = payload.get("public_url") or payload.get("url") or payload.get("file_url")
    if not storage_key or not public_url:
        raise StorageServiceError("Storage service returned an incomplete image response.")

    return StoredImage(storage_key=str(storage_key), public_url=str(public_url))


# Internal function to upload a video to the storage service, returning a StoredImage with the public URL and storage key
def _upload_video(file_storage, *, folder: str) -> StoredImage:
    if not file_storage or file_storage.filename == "":
        raise ValueError("Please choose a video to upload.")
    if not allowed_video_file(file_storage.filename):
        raise ValueError("Unsupported file type. Use mp4/webm/ogv.")

    filename = secure_filename(file_storage.filename) or "recipe-video"
    file_storage.stream.seek(0)
    file_bytes = file_storage.stream.read()

    try:
        response = requests.post(
            f"{_storage_base_url()}/files",
            headers=_storage_headers(),
            data={"folder": folder},
            files={"file": (filename, file_bytes, file_storage.mimetype or "application/octet-stream")},
            timeout=_storage_timeout(),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise StorageServiceError("Could not upload the recipe video right now. Please try again.") from exc
    except ValueError as exc:
        raise StorageServiceError("Storage service returned invalid video data.") from exc

    storage_key = payload.get("file_id") or payload.get("id") or payload.get("storage_key") or payload.get("key")
    public_url = payload.get("public_url") or payload.get("url") or payload.get("file_url")
    if not storage_key or not public_url:
        raise StorageServiceError("Storage service returned an incomplete video response.")

    return StoredImage(storage_key=str(storage_key), public_url=str(public_url))


# Upload a recipe image, returning a StoredImage with the public URL and storage key
def upload_recipe_image(file_storage) -> StoredImage:
    try:
        return _upload_image(file_storage, folder="recipes")
    except StorageServiceError as exc:
        current_app.logger.warning("Falling back to local recipe image storage: %s", exc)
        file_storage.stream.seek(0)
        filename = save_image(file_storage, current_app.config["UPLOAD_FOLDER"])
        public_url = current_app.config.get("LOCAL_UPLOADS_BASE_URL", "/static/uploads").rstrip("/")
        return StoredImage(storage_key="", public_url=f"{public_url}/{filename}")


# Upload a recipe step image, returning a StoredImage with the public URL and storage key
def upload_recipe_step_image(file_storage) -> StoredImage:
    try:
        return _upload_image(file_storage, folder="recipes/steps")
    except StorageServiceError as exc:
        current_app.logger.warning("Falling back to local recipe step image storage: %s", exc)
        file_storage.stream.seek(0)
        filename = save_image(file_storage, current_app.config["UPLOAD_FOLDER"])
        public_url = current_app.config.get("LOCAL_UPLOADS_BASE_URL", "/static/uploads").rstrip("/")
        return StoredImage(storage_key="", public_url=f"{public_url}/{filename}")


# Upload a recipe step video, returning a StoredImage with the public URL and storage key
def upload_recipe_step_video(file_storage) -> StoredImage:
    try:
        return _upload_video(file_storage, folder="recipes/steps/videos")
    except StorageServiceError as exc:
        current_app.logger.warning("Falling back to local recipe step video storage: %s", exc)
        file_storage.stream.seek(0)
        filename = save_video(file_storage, current_app.config["UPLOAD_FOLDER"])
        public_url = current_app.config.get("LOCAL_UPLOADS_BASE_URL", "/static/uploads").rstrip("/")
        return StoredImage(storage_key="", public_url=f"{public_url}/{filename}")


# Delete a recipe image from the storage service using its storage key
def delete_recipe_image(storage_key: str):
    if not storage_key:
        return

    try:
        response = requests.delete(
            f"{_storage_base_url()}/files/{quote(storage_key, safe='')}",
            headers=_storage_headers(),
            timeout=_storage_timeout(),
        )
        if response.status_code not in (200, 202, 204, 404):
            response.raise_for_status()
    except requests.RequestException as exc:
        raise StorageServiceError("Could not delete the old recipe image from storage.") from exc

from __future__ import annotations

import mimetypes
from pathlib import Path

from aicoding_shared.config import get_settings


class ObjectStorage:
    def __init__(self) -> None:
        self.settings = get_settings()

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        if self.settings.storage_backend == "minio":
            self._put_minio(key, data, content_type)
            return
        path = self._local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        if self.settings.storage_backend == "minio":
            return self._get_minio(key)
        return self._local_path(key).read_bytes()

    def exists(self, key: str) -> bool:
        if self.settings.storage_backend == "minio":
            try:
                self._get_minio(key)
                return True
            except Exception:
                return False
        return self._local_path(key).exists()

    def content_type(self, key: str) -> str:
        return mimetypes.guess_type(key)[0] or "application/octet-stream"

    def _local_path(self, key: str) -> Path:
        root = Path(self.settings.storage_local_root).resolve()
        path = (root / key).resolve()
        if root not in path.parents and path != root:
            raise ValueError("Invalid object key")
        return path

    def _client(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required when STORAGE_BACKEND=minio") from exc
        return boto3.client(
            "s3",
            endpoint_url=self.settings.minio_endpoint,
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
        )

    def _ensure_bucket(self, client) -> None:
        bucket = self.settings.minio_bucket
        buckets = client.list_buckets().get("Buckets", [])
        if not any(item.get("Name") == bucket for item in buckets):
            client.create_bucket(Bucket=bucket)

    def _put_minio(self, key: str, data: bytes, content_type: str | None) -> None:
        client = self._client()
        self._ensure_bucket(client)
        client.put_object(
            Bucket=self.settings.minio_bucket,
            Key=key,
            Body=data,
            ContentType=content_type or self.content_type(key),
        )

    def _get_minio(self, key: str) -> bytes:
        client = self._client()
        return client.get_object(Bucket=self.settings.minio_bucket, Key=key)["Body"].read()

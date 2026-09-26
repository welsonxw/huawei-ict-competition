"""Object storage: local disk for development, Huawei Cloud OBS (S3-compatible) in the cloud."""
import mimetypes
from pathlib import Path

from flask import current_app


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, key):
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("invalid key")
        return path

    def save(self, key, data: bytes, content_type=None):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, key) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key):
        return self._path(key).exists()


class OBSStorage:
    """Huawei Cloud OBS via its S3-compatible API."""

    def __init__(self, endpoint, bucket, access_key, secret_key):
        import boto3

        self.bucket = bucket
        self.client = boto3.client(
            "s3", endpoint_url=endpoint, aws_access_key_id=access_key, aws_secret_access_key=secret_key
        )

    def save(self, key, data: bytes, content_type=None):
        ctype = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=ctype)
        return key

    def read(self, key) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False


def get_storage():
    app = current_app
    if "storage" not in app.extensions:
        cfg = app.config
        if cfg["STORAGE_BACKEND"] == "obs":
            app.extensions["storage"] = OBSStorage(
                cfg["OBS_ENDPOINT"], cfg["OBS_BUCKET"], cfg["OBS_ACCESS_KEY"], cfg["OBS_SECRET_KEY"]
            )
        else:
            app.extensions["storage"] = LocalStorage(cfg["LOCAL_STORAGE_DIR"])
    return app.extensions["storage"]

"""The S3-compatible bucket the archive writes to.

The store covers what the per-target flow needs: whether a key exists, a JSON
document put and a file upload. Any failure to configure, authenticate to or
reach the bucket, and any failure of a later request, is a `StoreError`, which
ends the whole run.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ENDPOINT = "ARCHIVE_S3_ENDPOINT"
BUCKET = "ARCHIVE_S3_BUCKET"
ACCESS_KEY_ID = "ARCHIVE_S3_ACCESS_KEY_ID"
SECRET_ACCESS_KEY = "ARCHIVE_S3_SECRET_ACCESS_KEY"
PREFIX = "ARCHIVE_S3_PREFIX"
REQUIRED = (ENDPOINT, BUCKET, ACCESS_KEY_ID, SECRET_ACCESS_KEY)
DENIED_STATUSES = frozenset({401, 403})


class StoreError(Exception):
    """The bucket is not configured, does not exist, refuses the credentials or
    cannot be reached, or a request to it failed."""


class ArchiveStore:
    """Objects under one bucket and optional key prefix."""

    def __init__(self, client: Any, bucket: str, prefix: str = "") -> None:
        self._client = client
        self._bucket = bucket
        self._prefix = prefix.strip("/")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> ArchiveStore:
        """Build a store from the `ARCHIVE_S3_*` variables. boto3 belongs to
        the optional `archive` dependency group, so it is imported only here.
        The bucket is probed once, so a bad endpoint, credential or bucket name
        fails here rather than on the first target."""
        values = {name: environment.get(name, "").strip() for name in REQUIRED}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise StoreError(
                f"archive bucket is not configured: set {', '.join(missing)}"
            )
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=values[ENDPOINT],
            aws_access_key_id=values[ACCESS_KEY_ID],
            aws_secret_access_key=values[SECRET_ACCESS_KEY],
            region_name="auto",
            config=Config(
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=10,
                read_timeout=60,
            ),
        )
        with _translated():
            client.head_bucket(Bucket=values[BUCKET])
        return cls(client, values[BUCKET], environment.get(PREFIX, ""))

    def _key(self, key: str) -> str:
        return f"{self._prefix}/{key}" if self._prefix else key

    def exists(self, key: str) -> bool:
        """Whether an object is stored at `key`, by a HEAD request. Any failure
        other than not-found raises `StoreError`, as do the methods below."""
        from botocore.exceptions import ClientError

        with _translated():
            try:
                self._client.head_object(Bucket=self._bucket, Key=self._key(key))
            except ClientError as error:
                if _status(error) == 404:
                    return False
                raise
        return True

    def put_json(self, key: str, document: Mapping[str, Any]) -> None:
        body = json.dumps(document, indent=2, sort_keys=True).encode()
        with _translated():
            self._client.put_object(
                Bucket=self._bucket,
                Key=self._key(key),
                Body=body,
                ContentType="application/json",
            )

    def upload_file(self, path: Path, key: str) -> None:
        """Upload a file, as a multipart upload when it is large."""
        with _translated():
            self._client.upload_file(str(path), self._bucket, self._key(key))


def _status(error: Any) -> int | None:
    return error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")


@contextmanager
def _translated() -> Generator[None]:
    """Turn every boto failure into `StoreError`."""
    from boto3.exceptions import Boto3Error
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        yield
    except ClientError as error:
        if _status(error) in DENIED_STATUSES:
            raise StoreError(f"archive bucket denied access: {error}") from error
        raise StoreError(f"archive bucket request failed: {error}") from error
    except BotoCoreError as error:
        raise StoreError(f"cannot reach the archive bucket: {error}") from error
    except Boto3Error as error:
        raise StoreError(f"archive bucket request failed: {error}") from error

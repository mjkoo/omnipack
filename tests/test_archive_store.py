from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
import pytest
from boto3.exceptions import S3UploadFailedError
from botocore.awsrequest import AWSResponse
from botocore.stub import Stubber

from omnipack.archive.store import ArchiveStore, StoreError, StoreFailure

ENVIRONMENT = {
    "ARCHIVE_S3_ENDPOINT": "https://s3.example.test",
    "ARCHIVE_S3_BUCKET": "bucket",
    "ARCHIVE_S3_ACCESS_KEY_ID": "id",
    "ARCHIVE_S3_SECRET_ACCESS_KEY": "secret",
}


def make_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url="https://s3.example.test",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        region_name="auto",
    )


def stubbed(prefix: str = "") -> tuple[ArchiveStore, Stubber]:
    client = make_client()
    return ArchiveStore(client, "bucket", prefix), Stubber(client)


def construct_with(monkeypatch: pytest.MonkeyPatch, stubber_setup: Any) -> ArchiveStore:
    """Build from the environment against a stubbed client."""
    client = make_client()
    stubber = Stubber(client)
    stubber_setup(stubber)
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: client)
    with stubber:
        return ArchiveStore.from_environment(ENVIRONMENT)


@pytest.mark.parametrize("missing", sorted(ENVIRONMENT))
def test_missing_configuration_is_a_run_level_error(missing: str) -> None:
    environment = {k: v for k, v in ENVIRONMENT.items() if k != missing}
    with pytest.raises(StoreError, match=missing):
        ArchiveStore.from_environment(environment)


def test_blank_configuration_counts_as_missing() -> None:
    with pytest.raises(StoreError, match="ARCHIVE_S3_BUCKET"):
        ArchiveStore.from_environment({**ENVIRONMENT, "ARCHIVE_S3_BUCKET": " "})


def test_configuration_probes_the_bucket_and_builds_a_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = construct_with(
        monkeypatch,
        lambda stubber: stubber.add_response("head_bucket", {}, {"Bucket": "bucket"}),
    )
    assert isinstance(store, ArchiveStore)


def test_the_key_prefix_is_trimmed_like_the_other_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client()
    stubber = Stubber(client)
    stubber.add_response("head_bucket", {}, {"Bucket": "bucket"})
    stubber.add_response(
        "head_object", {}, {"Bucket": "bucket", "Key": "pre/a/manifest.json"}
    )
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: client)
    with stubber:
        store = ArchiveStore.from_environment(
            {**ENVIRONMENT, "ARCHIVE_S3_PREFIX": " pre/\n"}
        )
        assert store.exists("a/manifest.json")


def test_probe_failure_at_construction_is_a_run_level_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(StoreError) as caught:
        construct_with(
            monkeypatch,
            lambda stubber: stubber.add_client_error(
                "head_bucket", "404", http_status_code=404
            ),
        )

    assert caught.value.failure is StoreFailure.REQUEST_FAILED


def test_exists_is_true_when_head_succeeds() -> None:
    store, stubber = stubbed("pre")
    stubber.add_response(
        "head_object", {}, {"Bucket": "bucket", "Key": "pre/a/manifest.json"}
    )
    with stubber:
        assert store.exists("a/manifest.json")


def test_exists_is_false_on_not_found() -> None:
    store, stubber = stubbed()
    stubber.add_client_error("head_object", "404", http_status_code=404)
    with stubber:
        assert not store.exists("a")


@pytest.mark.parametrize("status", [401, 403])
def test_access_denied_is_a_run_level_error(status: int) -> None:
    store, stubber = stubbed()
    stubber.add_client_error("head_object", str(status), http_status_code=status)
    with stubber, pytest.raises(StoreError) as caught:
        store.exists("a")

    assert caught.value.failure is StoreFailure.DENIED


def test_head_server_error_is_a_run_level_error() -> None:
    store, stubber = stubbed()
    stubber.add_client_error("head_object", "500", http_status_code=500)
    with stubber, pytest.raises(StoreError):
        store.exists("a")


def test_unreachable_endpoint_is_a_run_level_error() -> None:
    with pytest.raises(StoreError) as caught:
        ArchiveStore.from_environment(
            {**ENVIRONMENT, "ARCHIVE_S3_ENDPOINT": "http://127.0.0.1:1"}
        )

    assert caught.value.failure is StoreFailure.UNREACHABLE


class EmptyBody:
    def stream(self, **_: Any) -> Any:
        return iter(())


def test_uploads_carry_no_checksum_unless_the_operation_requires_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cloud Storage rejects the default trailing checksums of boto3 uploads."""
    sent: list[dict[str, str]] = []
    real_client = boto3.client

    def answer(request: Any, **_: Any) -> AWSResponse:
        sent.append(dict(request.headers))
        return AWSResponse(request.url, 200, {}, EmptyBody())

    def client(*args: Any, **kwargs: Any) -> Any:
        built = real_client(*args, **kwargs)
        built.meta.events.register("before-send.s3", answer)
        return built

    monkeypatch.setattr(boto3, "client", client)
    store = ArchiveStore.from_environment(ENVIRONMENT)
    store.put_json("k.json", {"n": 1})

    put = sent[-1]
    assert not [name for name in put if name.lower().startswith("x-amz-checksum")]
    assert "x-amz-trailer" not in {name.lower() for name in put}


def test_put_json_failure_is_a_run_level_error() -> None:
    store, stubber = stubbed()
    stubber.add_client_error("put_object", "500", http_status_code=500)
    with stubber, pytest.raises(StoreError):
        store.put_json("k.json", {})


def test_put_json_writes_the_document() -> None:
    store, stubber = stubbed()
    document: dict[str, Any] = {"version": "1.0", "n": 1}
    body = json.dumps(document, indent=2, sort_keys=True).encode()
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": "bucket",
            "Key": "k.json",
            "Body": body,
            "ContentType": "application/json",
        },
    )
    with stubber:
        store.put_json("k.json", document)
    stubber.assert_no_pending_responses()


def test_upload_file_hands_the_file_to_the_client(tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []

    class Client:
        def upload_file(self, filename: str, bucket: str, key: str) -> None:
            calls.append((filename, bucket, key))

    path = tmp_path / "f"
    path.write_bytes(b"x")
    ArchiveStore(Client(), "bucket", "pre").upload_file(path, "a/f")
    assert calls == [(str(path), "bucket", "pre/a/f")]


def test_upload_failure_is_a_run_level_error(tmp_path: Path) -> None:
    class Client:
        def upload_file(self, filename: str, bucket: str, key: str) -> None:
            raise S3UploadFailedError("Failed to upload")

    path = tmp_path / "f"
    path.write_bytes(b"x")
    with pytest.raises(StoreError):
        ArchiveStore(Client(), "bucket").upload_file(path, "a/f")


def test_list_keys_pages_through_and_strips_the_prefix() -> None:
    store, stubber = stubbed("pre")
    first = datetime(2026, 1, 1, tzinfo=UTC)
    second = datetime(2026, 1, 2, tzinfo=UTC)
    request = {"Bucket": "bucket", "Prefix": "pre/apps/a/"}
    stubber.add_response(
        "list_objects_v2",
        {
            "IsTruncated": True,
            "NextContinuationToken": "t",
            "Contents": [{"Key": "pre/apps/a/x", "LastModified": first}],
        },
        request,
    )
    stubber.add_response(
        "list_objects_v2",
        {
            "IsTruncated": False,
            "Contents": [{"Key": "pre/apps/a/y", "LastModified": second}],
        },
        {**request, "ContinuationToken": "t"},
    )
    with stubber:
        assert store.list_keys("apps/a/") == [
            ("apps/a/x", first),
            ("apps/a/y", second),
        ]


def test_list_keys_of_an_empty_prefix_is_empty() -> None:
    store, stubber = stubbed()
    stubber.add_response("list_objects_v2", {"IsTruncated": False}, None)
    with stubber:
        assert store.list_keys("apps/") == []


def test_list_failure_is_a_run_level_error() -> None:
    store, stubber = stubbed()
    stubber.add_client_error("list_objects_v2", "500", http_status_code=500)
    with stubber, pytest.raises(StoreError):
        store.list_keys("apps/")


def test_delete_sends_keys_in_batches_of_a_thousand() -> None:
    store, stubber = stubbed("pre")
    keys = [f"k{n}" for n in range(1001)]

    def request(names: list[str]) -> dict[str, Any]:
        return {
            "Bucket": "bucket",
            "Delete": {"Objects": [{"Key": f"pre/{n}"} for n in names], "Quiet": True},
        }

    stubber.add_response("delete_objects", {}, request(keys[:1000]))
    stubber.add_response("delete_objects", {}, request(keys[1000:]))
    with stubber:
        store.delete(keys)
    stubber.assert_no_pending_responses()


def test_delete_of_no_keys_makes_no_request() -> None:
    store, stubber = stubbed()
    with stubber:
        store.delete([])


def test_a_per_key_delete_error_is_a_failure() -> None:
    store, stubber = stubbed()
    stubber.add_response(
        "delete_objects",
        {"Errors": [{"Key": "a", "Code": "AccessDenied", "Message": "no"}]},
        None,
    )
    with stubber, pytest.raises(StoreError) as caught:
        store.delete(["a"])

    assert caught.value.failure is StoreFailure.REQUEST_FAILED


def test_delete_denied_is_a_run_level_error() -> None:
    store, stubber = stubbed()
    stubber.add_client_error("delete_objects", "403", http_status_code=403)
    with stubber, pytest.raises(StoreError) as caught:
        store.delete(["a"])

    assert caught.value.failure is StoreFailure.DENIED

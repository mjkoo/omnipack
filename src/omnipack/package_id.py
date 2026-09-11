"""Resolve Android package IDs from release APK manifests.

The binary Android XML and ZIP parsing code is adapted from RJNY's package-id
resolver: https://github.com/RJNY/Obtainium-Emulation-Pack/blob/main/scripts/package_id.py
Fetched source blob: df1b2f8ebb9a83368c4609ec8185e18828d067ef
https://api.github.com/repos/RJNY/Obtainium-Emulation-Pack/git/blobs/df1b2f8ebb9a83368c4609ec8185e18828d067ef
It is free and unencumbered software released into the public domain;
see <https://unlicense.org>.
"""

from __future__ import annotations

import re
import struct
import zlib
from typing import Any

from omnipack.http import HttpClient, HttpError

MAX_APK_FULL_DOWNLOAD = 40 * 1024 * 1024
ZIP_TAIL_SIZE = 128 * 1024
ZIP_EOCD_SIG = b"PK\x05\x06"
ZIP_CD_SIG = b"PK\x01\x02"
ZIP_LOCAL_SIG = b"PK\x03\x04"
AXML_RES_XML = 0x0003
AXML_STRING_POOL = 0x0001
AXML_START_ELEMENT = 0x0102
AXML_TYPE_STRING = 0x03
PACKAGE_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")


def resolve_release_assets(
    http: HttpClient,
    release: dict[str, Any],
    filename_pattern: str = "",
    report: dict[str, Any] | None = None,
    project_url: str | None = None,
) -> str:
    """Return the one package ID declared by every eligible APK in a release."""
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise TypeError("latest release has no asset list")
    pattern = re.compile(filename_pattern) if filename_pattern else None
    eligible: list[tuple[str, str]] = []
    filtered: list[str] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name, url = asset.get("name"), asset.get("browser_download_url")
        if isinstance(name, str) and name.lower().endswith(".apk"):
            if pattern is not None and pattern.search(name) is None:
                filtered.append(name)
                continue
            if not isinstance(url, str) or not url:
                raise ValueError(f"eligible APK {name!r} has no download URL")
            eligible.append((name, url))
    if report is not None and filtered:
        report.setdefault("filteredAssets", []).append(
            {"url": project_url, "names": sorted(filtered)}
        )
    if not eligible:
        raise ValueError("latest release has no eligible APK assets")
    resolved: list[str] = []
    for name, url in eligible:
        try:
            manifest = extract_android_manifest_from_apk_url(http, url)
            resolved.append(parse_axml_package_id(manifest))
        except (
            HttpError,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
            struct.error,
            zlib.error,
        ) as error:
            raise ValueError(f"cannot read eligible APK {name!r}: {error}") from error
    unique = set(resolved)
    if len(unique) != 1:
        raise ValueError(
            "eligible APK assets declare different package ids: "
            + ", ".join(sorted(unique))
        )
    return resolved[0]


def extract_android_manifest_from_apk_url(http: HttpClient, url: str) -> bytes:
    """Read an APK manifest through byte ranges, with a bounded full fallback."""
    try:
        head = http.get(url, method="HEAD", max_bytes=0)
    except HttpError:
        head = None
    if head is not None:
        length = head.headers.get("Content-Length")
        if (
            length is not None
            and "bytes" in head.headers.get("Accept-Ranges", "").lower()
        ):
            try:
                size = int(length)
                if size <= 0:
                    raise ValueError("invalid APK content length")
                return _extract_manifest_with_ranges(http, url, size)
            except HttpError, ValueError, struct.error, zlib.error:
                pass
    response = http.get(url, max_bytes=MAX_APK_FULL_DOWNLOAD)
    return extract_android_manifest_from_apk(response.body)


def _extract_manifest_with_ranges(http: HttpClient, url: str, size: int) -> bytes:
    tail_start = max(0, size - ZIP_TAIL_SIZE)
    tail = _range(http, url, tail_start, size - 1)
    eocd = tail.rfind(ZIP_EOCD_SIG)
    if eocd < 0:
        raise ValueError("ZIP end-of-central-directory not found")
    central_size, central_offset = struct.unpack_from("<II", tail, eocd + 12)
    if central_offset + central_size > size:
        raise ValueError("invalid ZIP central directory bounds")
    central = _range(http, url, central_offset, central_offset + central_size - 1)
    offset, compressed_size, method = _find_zip_entry(central, "AndroidManifest.xml")
    local = _range(
        http, url, offset, min(size - 1, offset + 30 + 512 + compressed_size - 1)
    )
    return _inflate_local_entry(local, compressed_size, method)


def _range(http: HttpClient, url: str, start: int, end: int) -> bytes:
    response = http.get(
        url, headers={"Range": f"bytes={start}-{end}"}, max_bytes=end - start + 1
    )
    if response.status != 206:
        raise ValueError(f"server ignored byte range with status {response.status}")
    return response.body


def parse_axml_package_id(data: bytes) -> str:
    if len(data) < 8:
        raise ValueError("AXML too short")
    chunk_type, header_size, file_size = struct.unpack_from("<HHI", data, 0)
    if chunk_type != AXML_RES_XML:
        raise ValueError(f"not an AXML document (type={chunk_type:#x})")
    if file_size > len(data):
        raise ValueError("AXML size exceeds buffer")
    pos, strings = header_size, []
    while pos + 8 <= len(data):
        chunk_type, chunk_header, chunk_size = struct.unpack_from("<HHI", data, pos)
        if chunk_size < 8 or pos + chunk_size > len(data):
            raise ValueError("invalid AXML chunk")
        if chunk_type == AXML_STRING_POOL:
            strings = _parse_string_pool(data, pos, chunk_header, chunk_size)
        elif chunk_type == AXML_START_ELEMENT:
            package_id = _package_from_start_element(data, pos, strings)
            if package_id:
                return package_id
        pos += chunk_size
    raise ValueError("package attribute not found in AndroidManifest.xml")


def _parse_string_pool(
    data: bytes, pos: int, header_size: int, chunk_size: int
) -> list[str]:
    if header_size < 28:
        raise ValueError("string pool header too small")
    count, _styles, flags, strings_start, _style_start = struct.unpack_from(
        "<IIIII", data, pos + 8
    )
    offsets_pos = pos + header_size
    if offsets_pos + count * 4 > pos + chunk_size:
        raise ValueError("string pool offsets overrun")
    offsets = [
        struct.unpack_from("<I", data, offsets_pos + i * 4)[0] for i in range(count)
    ]
    base, strings = pos + strings_start, []
    for offset in offsets:
        cursor = base + offset
        if cursor >= pos + chunk_size:
            strings.append("")
            continue
        if flags & (1 << 8):
            _chars, cursor = _read_utf8_len(data, cursor)
            length, cursor = _read_utf8_len(data, cursor)
            strings.append(
                data[cursor : cursor + length].decode("utf-8", errors="replace")
            )
        else:
            length, cursor = _read_utf16_len(data, cursor)
            strings.append(
                data[cursor : cursor + length * 2].decode("utf-16-le", errors="replace")
            )
    return strings


def _read_utf8_len(data: bytes, pos: int) -> tuple[int, int]:
    first = data[pos]
    return (
        (((first & 0x7F) << 8) | data[pos + 1], pos + 2)
        if first & 0x80
        else (first, pos + 1)
    )


def _read_utf16_len(data: bytes, pos: int) -> tuple[int, int]:
    first = struct.unpack_from("<H", data, pos)[0]
    if first & 0x8000:
        return ((first & 0x7FFF) << 16) | struct.unpack_from("<H", data, pos + 2)[
            0
        ], pos + 4
    return first, pos + 2


def _package_from_start_element(
    data: bytes, pos: int, strings: list[str]
) -> str | None:
    if pos + 36 > len(data):
        return None
    start, size, count = struct.unpack_from("<HHH", data, pos + 24)
    if size < 20:
        return None
    for index in range(count):
        attribute = pos + 16 + start + index * size
        if attribute + 20 > len(data):
            break
        _namespace, name, _raw = struct.unpack_from("<III", data, attribute)
        _value_size, _reserved, data_type = struct.unpack_from(
            "<HBB", data, attribute + 12
        )
        value = struct.unpack_from("<I", data, attribute + 16)[0]
        if (
            name < len(strings)
            and strings[name] == "package"
            and data_type == AXML_TYPE_STRING
            and value < len(strings)
            and _is_valid_package_id(strings[value])
        ):
            return strings[value]
    return None


def _is_valid_package_id(value: str) -> bool:
    return bool(
        value
        and not value.startswith("android.")
        and "${" not in value
        and not value.startswith("@")
        and PACKAGE_NAME_RE.fullmatch(value)
    )


def extract_android_manifest_from_apk(apk_data: bytes) -> bytes:
    eocd = apk_data.rfind(ZIP_EOCD_SIG)
    if eocd < 0:
        raise ValueError("ZIP end-of-central-directory not found")
    central_size, central_offset = struct.unpack_from("<II", apk_data, eocd + 12)
    central = apk_data[central_offset : central_offset + central_size]
    offset, compressed_size, method = _find_zip_entry(central, "AndroidManifest.xml")
    return _inflate_local_entry(apk_data[offset:], compressed_size, method)


def _find_zip_entry(central: bytes, name: str) -> tuple[int, int, int]:
    pos, target = 0, name.encode()
    while pos + 46 <= len(central):
        if central[pos : pos + 4] != ZIP_CD_SIG:
            break
        method = struct.unpack_from("<H", central, pos + 10)[0]
        compressed_size = struct.unpack_from("<I", central, pos + 20)[0]
        name_length, extra_length, comment_length = struct.unpack_from(
            "<HHH", central, pos + 28
        )
        offset = struct.unpack_from("<I", central, pos + 42)[0]
        if central[pos + 46 : pos + 46 + name_length] == target:
            return offset, compressed_size, method
        pos += 46 + name_length + extra_length + comment_length
    raise ValueError(f"{name} not found in APK")


def _inflate_local_entry(local: bytes, compressed_size: int, method: int) -> bytes:
    if local[:4] != ZIP_LOCAL_SIG:
        raise ValueError("invalid ZIP local header")
    name_length, extra_length = struct.unpack_from("<HH", local, 26)
    start = 30 + name_length + extra_length
    compressed = local[start : start + compressed_size]
    if len(compressed) < compressed_size:
        raise ValueError("truncated compressed entry data")
    if method == 0:
        return compressed
    if method == 8:
        return zlib.decompress(compressed, -15)
    raise ValueError(f"unsupported ZIP compression method {method}")

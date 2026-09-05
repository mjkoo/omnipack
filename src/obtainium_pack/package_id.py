"""APK package-id resolution.

Vendors RJNY's APK manifest parser (reads the Android package id from an
APK's central directory without downloading the whole file), with
attribution to be added alongside the vendored source once it is copied in.
"""

from __future__ import annotations


def resolve_package_id(apk_url: str) -> str:
    """Return the Android package id declared in the APK at `apk_url`."""
    raise NotImplementedError

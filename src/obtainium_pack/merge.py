"""Union sources by package id, apply precedence and the denylist.

Precedence when the same package id appears in multiple sources: overlay >
extras > RJNY > BBoi > generated (codm).
"""

from __future__ import annotations

from obtainium_pack.model import App


def merge(sources: dict[str, list[App]], denylist: list[dict[str, str]]) -> list[App]:
    """Union `sources` by package id honoring precedence, then apply `denylist`."""
    raise NotImplementedError

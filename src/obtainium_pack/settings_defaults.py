"""Canonical per-source settings defaults used by pack rendering.

The key sets and values were seeded from Obtainium v1.6.14 and checked against
the exports produced by RJNY/Obtainium-Emulation-Pack. Obtainium source schema:
https://github.com/ImranR98/Obtainium/tree/v1.6.14/lib/app_sources
"""

from __future__ import annotations

from typing import Any, Final

OBTAINIUM_VERSION: Final = "1.6.14"

_COMMON: dict[str, Any] = {
    "trackOnly": False,
    "versionExtractionRegEx": "",
    "matchGroupToUse": "",
    "versionDetection": True,
    "releaseDateAsVersion": False,
    "useVersionCodeAsOSVersion": False,
    "apkFilterRegEx": "",
    "invertAPKFilter": False,
    "autoApkFilterByArch": True,
    "appName": "",
    "appAuthor": "",
    "shizukuPretendToBeGooglePlay": False,
    "allowInsecure": False,
    "exemptFromBackgroundUpdates": False,
    "skipUpdateNotifications": False,
    "about": "",
    "refreshBeforeDownload": False,
    "includeZips": False,
    "zippedApkFilterRegEx": "",
}

SETTINGS_DEFAULTS: Final[dict[str, dict[str, Any]]] = {
    "GitHub": {
        "includePrereleases": False,
        "fallbackToOlderReleases": True,
        "filterReleaseTitlesByRegEx": "",
        "filterReleaseNotesByRegEx": "",
        "verifyLatestTag": False,
        "sortMethodChoice": "date",
        "useLatestAssetDateAsReleaseDate": False,
        "releaseTitleAsVersion": False,
        "github-creds": "",
        "GHReqPrefix": "",
        **_COMMON,
    },
    "HTML": {
        "intermediateLink": [],
        "customLinkFilterRegex": "",
        "filterByLinkText": False,
        "matchLinksOutsideATags": False,
        "skipSort": False,
        "reverseSort": False,
        "sortByLastLinkSegment": False,
        "versionExtractWholePage": False,
        "requestHeader": [{"requestHeader": "User-Agent: Obtainium/1.0"}],
        "defaultPseudoVersioningMethod": "partialAPKHash",
        **_COMMON,
    },
}

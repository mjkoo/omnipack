import pytest

from omnipack.urls import normalize_project_url


@pytest.mark.parametrize(
    ("url", "normalized"),
    [
        ("https://Example.com/Owner/Repo", "example.com/Owner/Repo"),
        ("http://www.example.com/Owner/Repo", "example.com/Owner/Repo"),
        ("https://example.com/Owner/Repo/", "example.com/Owner/Repo"),
        ("https://example.com/Owner/Repo.git", "example.com/Owner/Repo"),
        ("https://GitHub.com/OWNER/Repo", "github.com/owner/repo"),
        ("https://github.com/Owner/Repo/releases", "github.com/owner/repo"),
        ("https://github.com/Owner/Repo.git/releases", "github.com/owner/repo"),
        ("https://github.com/Owner/Repo?tab=readme", "github.com/owner/repo"),
        ("https://github.com/Owner/Repo#readme", "github.com/owner/repo"),
        (
            "http://WWW.GITHUB.COM/Owner/Repo.git/releases/latest?x=1#download",
            "github.com/owner/repo",
        ),
    ],
)
def test_normalize_project_url(url: str, normalized: str) -> None:
    assert normalize_project_url(url) == normalized


@pytest.mark.parametrize(
    ("left", "right", "same"),
    [
        (
            "http://github.com/SomeOwner/SomeRepo.git/",
            "https://WWW.GITHUB.COM/someowner/somerepo",
            True,
        ),
        ("https://codeberg.org/Owner/Repo", "https://codeberg.org/owner/repo", False),
        ("https://github.com/owner/one", "https://github.com/owner/two", False),
    ],
)
def test_normalized_urls_identify_the_same_project(
    left: str, right: str, same: bool
) -> None:
    assert (normalize_project_url(left) == normalize_project_url(right)) is same


@pytest.mark.parametrize(
    ("host", "suffix"),
    [
        ("gitlab.com", "?view=1"),
        ("example.com", "?view=1"),
        ("gitlab.com", "#section"),
        ("example.com", "#section"),
        ("github.com", ":443"),
        ("gitlab.com", ":443"),
        ("example.com", ":443"),
    ],
)
def test_project_identity_retains_non_github_query_fragment_and_every_port(
    host: str, suffix: str
) -> None:
    original = f"https://{host}/Owner/Repo"
    changed = (
        f"https://{host}:443/Owner/Repo" if suffix == ":443" else original + suffix
    )
    assert normalize_project_url(original) != normalize_project_url(changed)

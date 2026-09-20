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
        (
            "https://www.gitlab.com/Group/Project",
            "https://gitlab.com/Group/Project",
            True,
        ),
        (
            "https://gitlab.com/Owner/Repo",
            "https://gitlab.com/Owner/Repo?view=1",
            False,
        ),
        (
            "https://example.com/Owner/Repo",
            "https://example.com/Owner/Repo?view=1",
            False,
        ),
        (
            "https://gitlab.com/Owner/Repo",
            "https://gitlab.com/Owner/Repo#section",
            False,
        ),
        (
            "https://example.com/Owner/Repo",
            "https://example.com/Owner/Repo#section",
            False,
        ),
        ("https://github.com/Owner/Repo", "https://github.com:443/Owner/Repo", False),
        ("https://gitlab.com/Owner/Repo", "https://gitlab.com:443/Owner/Repo", False),
        ("https://example.com/Owner/Repo", "https://example.com:443/Owner/Repo", False),
    ],
)
def test_normalized_urls_identify_the_same_project(
    left: str, right: str, same: bool
) -> None:
    assert (normalize_project_url(left) == normalize_project_url(right)) is same

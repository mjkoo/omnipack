import pytest

from omnipack.urls import normalize_project_url, project_urls_equal


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


def test_github_project_comparison_folds_scheme_owner_and_repo_case() -> None:
    assert project_urls_equal(
        "http://github.com/SomeOwner/SomeRepo.git/",
        "https://WWW.GITHUB.COM/someowner/somerepo",
    )


def test_non_github_path_comparison_preserves_case() -> None:
    assert not project_urls_equal(
        "https://codeberg.org/Owner/Repo", "https://codeberg.org/owner/repo"
    )


def test_different_projects_do_not_compare_equal() -> None:
    assert not project_urls_equal(
        "https://github.com/owner/one", "https://github.com/owner/two"
    )

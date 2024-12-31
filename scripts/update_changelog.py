import datetime as dt
import os
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

import git
import github.PullRequest
import github.Repository
from github import Github
from jinja2 import Template

CURRENT_FILE = Path(__file__)
ROOT = CURRENT_FILE.parents[1]
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
GIT_BRANCH = os.getenv("GITHUB_REF_NAME")


def main() -> None:
    """
    Script entry point.
    """
    # Generate changelog for PRs merged yesterday
    merged_date = dt.date.today() - dt.timedelta(days=1)
    repo = Github(login_or_token=GITHUB_TOKEN).get_repo(GITHUB_REPO)
    merged_pulls = list(iter_pulls(repo, merged_date))
    if not merged_pulls:
        return

    # Group pull requests by type of change
    grouped_pulls = group_pulls_by_change_type(merged_pulls)
    if not any(grouped_pulls.values()):
        return

    # Generate portion of markdown
    release_changes_summary = generate_md(grouped_pulls)

    # Update CHANGELOG.md file
    release = f"{merged_date:%Y.%m.%d}"
    changelog_path = ROOT / "CHANGELOG.md"
    write_changelog(changelog_path, release, release_changes_summary)

    # Update version
    setup_py_path = ROOT / "pyproject.toml"
    update_version(setup_py_path, release)

    # Run uv lock
    uv_lock_path = ROOT / "uv.lock"
    subprocess.run(["uv", "lock", "--no-upgrade"], cwd=ROOT, check=False)

    # Commit changes, create tag and push
    update_git_repo([changelog_path, setup_py_path, uv_lock_path], release)

    # Create GitHub release
    repo.create_git_release(
        tag=release,
        name=release,
        message=release_changes_summary,
    )


def iter_pulls(
    repo: github.Repository.Repository,
    merged_date: dt.date,
) -> Iterable[github.PullRequest.PullRequest]:
    """Fetch merged pull requests at the date we're interested in."""
    recent_pulls = repo.get_pulls(
        state="closed",
        sort="updated",
        direction="desc",
    ).get_page(0)
    for pull in recent_pulls:
        if pull.merged and pull.merged_at.date() == merged_date:
            yield pull


def group_pulls_by_change_type(
    pull_requests_list: list[github.PullRequest.PullRequest],
) -> dict[str, list[github.PullRequest.PullRequest]]:
    """Group pull request by change type."""
    grouped_pulls = {
        "Changed": [],
        "Fixed": [],
        "Documentation": [],
        "Updated": [],
    }
    for pull in pull_requests_list:
        label_names = {label.name for label in pull.labels}
        if "project infrastructure" in label_names:
            # Don't mention it in the changelog
            continue
        if "update" in label_names:
            group_name = "Updated"
        elif "bug" in label_names:
            group_name = "Fixed"
        elif "docs" in label_names:
            group_name = "Documentation"
        else:
            group_name = "Changed"
        grouped_pulls[group_name].append(pull)
    return grouped_pulls


def generate_md(grouped_pulls: dict[str, list[github.PullRequest.PullRequest]]) -> str:
    """Generate markdown file from Jinja template."""
    changelog_template = ROOT / ".github" / "changelog-template.md"
    template = Template(changelog_template.read_text(), autoescape=True)
    return template.render(grouped_pulls=grouped_pulls)


def write_changelog(file_path: Path, release: str, content: str) -> None:
    """Write Release details to the changelog file."""
    content = f"## {release}\n{content}"
    old_content = file_path.read_text()
    updated_content = old_content.replace(
        "<!-- GENERATOR_PLACEHOLDER -->",
        f"<!-- GENERATOR_PLACEHOLDER -->\n\n{content}",
    )
    file_path.write_text(updated_content)


def update_version(file_path: Path, release: str) -> None:
    """Update template version in pyproject.toml."""
    old_content = file_path.read_text()
    updated_content = re.sub(
        r'\nversion = "\d+\.\d+\.\d+"\n',
        f'\nversion = "{release}"\n',
        old_content,
    )
    file_path.write_text(updated_content)


def update_git_repo(paths: list[Path], release: str) -> None:
    """Commit, tag changes in git repo and push to origin."""
    repo = git.Repo(ROOT)
    for path in paths:
        repo.git.add(path)
    message = f"Release {release}"

    user = repo.git.config("--get", "user.name")
    email = repo.git.config("--get", "user.email")

    repo.git.commit(
        m=message,
        author=f"{user} <{email}>",
    )
    repo.git.tag("-a", release, m=message)
    server = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    repo.git.push(server, GIT_BRANCH)
    repo.git.push("--tags", server, GIT_BRANCH)


if __name__ == "__main__":
    if GITHUB_REPO is None:
        msg = "No github repo, please set the environment variable GITHUB_REPOSITORY"
        raise RuntimeError(msg)
    if GIT_BRANCH is None:
        msg = "No git branch set, please set the GITHUB_REF_NAME environment variable"
        raise RuntimeError(msg)
    main()

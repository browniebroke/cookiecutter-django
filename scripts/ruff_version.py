from __future__ import annotations

import subprocess
from pathlib import Path

import tomllib

ROOT = Path(__file__).parent.parent
TEMPLATED_ROOT = ROOT / "{{cookiecutter.project_slug}}"
REQUIREMENTS_LOCAL_TXT = TEMPLATED_ROOT / "requirements" / "local.txt"
TEMPLATE_PRE_COMMIT_CONFIG = ROOT / ".pre-commit-config.yaml"
PRE_COMMIT_CONFIG = TEMPLATED_ROOT / ".pre-commit-config.yaml"
PYPROJECT_TOML = ROOT / "pyproject.toml"


def main() -> None:
    new_version = get_requirements_txt_version()
    old_version = get_pyproject_toml_version()
    if old_version == new_version:
        return

    update_ruff_version(old_version, new_version)
    subprocess.run(["uv", "lock", "--no-upgrade"], cwd=ROOT, check=False)  # noqa: S603,S607


def get_requirements_txt_version() -> str:
    content = REQUIREMENTS_LOCAL_TXT.read_text()
    for line in content.split("\n"):
        if line.startswith("ruff"):
            return line.split(" ")[0].split("==")[1]
    raise RuntimeError("Could not find ruff version in requirements/local.txt")


def get_pyproject_toml_version() -> str:
    data = tomllib.loads(PYPROJECT_TOML.read_text())
    for dependency in data["project"]["dependencies"]:
        if dependency.startswith("ruff=="):
            return dependency.split("==")[1]
    raise RuntimeError("Could not find ruff version in pyproject.toml")


def update_ruff_version(old_version: str, new_version: str) -> None:
    # Update pyproject.toml
    new_content = PYPROJECT_TOML.read_text().replace(
        f"ruff=={old_version}",
        f"ruff=={new_version}",
    )
    PYPROJECT_TOML.write_text(new_content)
    # Update pre-commit configs
    for config_file in [PRE_COMMIT_CONFIG, TEMPLATE_PRE_COMMIT_CONFIG]:
        new_content = config_file.read_text().replace(
            f"repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v{old_version}",
            f"repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v{new_version}",
        )
        config_file.write_text(new_content)


if __name__ == "__main__":
    main()

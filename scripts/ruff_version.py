import subprocess
from pathlib import Path

import tomllib

ROOT = Path(__file__).parent.parent
TEMPLATED_ROOT = ROOT / "{{cookiecutter.project_slug}}"
REQUIREMENTS_LOCAL_TXT = TEMPLATED_ROOT / "requirements" / "local.txt"
PRE_COMMIT_CONFIG = TEMPLATED_ROOT / ".pre-commit-config.yaml"
PYPROJECT_TOML = ROOT / "pyproject.toml"


def main():
    new_version = get_requirements_txt_version()
    old_version = get_pyproject_toml_version()
    if old_version == new_version:
        return

    update_ruff_version(old_version, new_version)
    subprocess.run(["uv", "lock", "--no-upgrade"], cwd=ROOT, check=False)  # noqa: S603,S607


def get_requirements_txt_version():
    content = REQUIREMENTS_LOCAL_TXT.read_text()
    for line in content.split("\n"):
        if line.startswith("ruff"):
            return line.split(" ")[0].split("==")[1]
    return None


def get_pyproject_toml_version():
    data = tomllib.loads(PYPROJECT_TOML.read_text())
    for dependency in data["project"]["dependencies"]:
        if dependency.startswith("ruff=="):
            return dependency.split("==")[1]
    raise RuntimeError("Could not find version in pyproject.toml")


def update_ruff_version(old_version, new_version):
    # Update pyproject.toml
    new_content = PYPROJECT_TOML.read_text().replace(
        f"ruff=={old_version}",
        f"ruff=={new_version}",
    )
    PYPROJECT_TOML.write_text(new_content)
    # Update pre-commit config
    new_content = PRE_COMMIT_CONFIG.read_text().replace(
        f"repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v{old_version}",
        f"repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v{new_version}",
    )
    PRE_COMMIT_CONFIG.write_text(new_content)


if __name__ == "__main__":
    main()

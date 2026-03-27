#!/usr/bin/env python
"""Release script: bump version → build → git tag."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYPROJECT = ROOT / "pyproject.toml"
DEFAULT_CONFIG = ROOT / "config.default.json"


def get_current_version() -> str:
    data = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    return data["version"]


def bump_version(version: str, part: str) -> str:
    major, minor, patch = map(int, version.split("."))
    match part:
        case "major":
            return f"{major + 1}.0.0"
        case "minor":
            return f"{major}.{minor + 1}.0"
        case "patch":
            return f"{major}.{minor}.{patch + 1}"
        case _:
            raise ValueError(f"Unknown version part: {part}")


def update_pyproject(new_version: str) -> None:
    content = PYPROJECT.read_text(encoding="utf-8")
    content = re.sub(r'(version\s*=\s*")[^"]+(")', rf'\g<1>{new_version}\g<2>', content)
    PYPROJECT.write_text(content, encoding="utf-8")


def update_default_config(new_version: str) -> None:
    data = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    data["version"] = new_version
    DEFAULT_CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("major", "minor", "patch"):
        print("Usage: python scripts/release.py [major|minor|patch]")
        sys.exit(1)

    part = sys.argv[1]
    current = get_current_version()
    new_version = bump_version(current, part)

    print(f"Bumping version: {current} → {new_version}")
    update_pyproject(new_version)
    update_default_config(new_version)

    # Run full build
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], cwd=ROOT, check=True)

    # Build installer
    print("\nBuilding Windows installer...")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_installer.py")], cwd=ROOT, check=False)

    # Git tag
    subprocess.run(["git", "add", str(PYPROJECT), str(DEFAULT_CONFIG)], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", f"chore: release v{new_version}"], cwd=ROOT, check=True)
    subprocess.run(["git", "tag", f"v{new_version}"], cwd=ROOT, check=True)

    print(f"\n[SUCCESS] Released v{new_version}")
    print("To push: git push origin main --tags")


if __name__ == "__main__":
    main()

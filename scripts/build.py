#!/usr/bin/env python
"""Build script: lint → type check → test → package."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run(cmd: list[str], description: str, check: bool = True) -> int:
    print(f"\n{'=' * 60}")
    print(f"  {description}")
    print(f"{'=' * 60}")
    result = subprocess.run(cmd, cwd=ROOT)
    if check and result.returncode != 0:
        print(f"\n[FAILED] {description} — exit code {result.returncode}")
        sys.exit(result.returncode)
    return result.returncode


def main() -> None:
    print("TexPaste build pipeline starting…")

    # 1. Lint
    run([sys.executable, "-m", "ruff", "check", "src/"], "Ruff lint")

    # 2. Format check
    run([sys.executable, "-m", "ruff", "format", "--check", "src/"], "Ruff format check")

    # 3. Type check
    run([sys.executable, "-m", "mypy", "src/utils/", "src/models/", "--strict"], "mypy type check")

    # 4. Unit tests
    run(
        [sys.executable, "-m", "pytest", "tests/unit/", "-v", "--tb=short",
         "-m", "not integration"],
        "Unit tests",
    )

    # 5. Package
    run([sys.executable, "-m", "PyInstaller", "texpaste.spec", "--clean", "--noconfirm"], "PyInstaller packaging")

    print("\n[SUCCESS] Build complete — dist/TexPaste.exe")


if __name__ == "__main__":
    main()

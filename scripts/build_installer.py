#!/usr/bin/env python
"""Build Windows installer using Inno Setup.

This script:
1. Checks that dist/TexPaste.exe exists
2. Reads version from config.default.json
3. Updates setup.iss with the correct version
4. Calls ISCC.exe to compile the installer

Prerequisites:
- Inno Setup 6.x installed (ISCC.exe in PATH)
- dist/TexPaste.exe built via build.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DIST_DIR = ROOT / "dist"
INSTALLER_DIR = ROOT / "installer"
CONFIG_FILE = ROOT / "config.default.json"
SETUP_ISS = INSTALLER_DIR / "setup.iss"


def get_version() -> str:
    """Read version from config.default.json."""
    data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return data["version"]


def check_prerequisites() -> bool:
    """Check that all prerequisites are met."""
    errors = []

    # Check TexPaste.exe exists
    exe_path = DIST_DIR / "TexPaste.exe"
    if not exe_path.exists():
        errors.append("dist/TexPaste.exe not found. Run 'python scripts/build.py' first.")

    # Check ISCC.exe is available
    if not shutil.which("ISCC.exe"):
        errors.append(
            "ISCC.exe not found in PATH. "
            "Install Inno Setup 6.x from https://jrsoftware.org/isdl.php"
        )

    # Check setup.iss exists
    if not SETUP_ISS.exists():
        errors.append(f"setup.iss not found at {SETUP_ISS}")

    if errors:
        print("[ERROR] Prerequisites check failed:\n")
        for error in errors:
            print(f"  - {error}")
        return False

    return True


def update_setup_version(version: str) -> None:
    """Update version in setup.iss file."""
    content = SETUP_ISS.read_text(encoding="utf-8")

    # Update #define MyAppVersion line
    content = re.sub(
        r'#define MyAppVersion "[^"]+"',
        f'#define MyAppVersion "{version}"',
        content
    )

    SETUP_ISS.write_text(content, encoding="utf-8")
    print(f"Updated setup.iss with version {version}")


def build_installer() -> int:
    """Build the installer using Inno Setup."""
    version = get_version()
    print(f"Building TexPaste installer v{version}\n")

    if not check_prerequisites():
        return 1

    # Update version in setup.iss
    update_setup_version(version)

    # Call ISCC.exe
    print("\nCompiling installer with Inno Setup...\n")
    result = subprocess.run(
        ["ISCC.exe", str(SETUP_ISS)],
        cwd=ROOT,
    )

    if result.returncode == 0:
        output_file = DIST_DIR / f"TexPaste-Setup-{version}.exe"
        print(f"\n[SUCCESS] Installer created: {output_file}")
        print(f"Size: {output_file.stat().st_size / (1024*1024):.1f} MB")
    else:
        print(f"\n[FAILED] Inno Setup compilation failed with code {result.returncode}")

    return result.returncode


if __name__ == "__main__":
    sys.exit(build_installer())
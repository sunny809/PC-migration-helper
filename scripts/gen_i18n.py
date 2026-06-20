"""Generate Qt translation files (.ts) from source code.

Usage:
    python scripts/gen_i18n.py

This script uses pyside6-lupdate to extract translatable strings
from the source code and generate .ts translation files.
"""

import os
import subprocess
import sys


def generate_translations():
    """Generate .ts translation files from source code."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    i18n_dir = os.path.join(project_root, "assets", "i18n")
    os.makedirs(i18n_dir, exist_ok=True)

    # Source files to scan
    src_dir = os.path.join(project_root, "src")

    # Languages to generate
    languages = ["zh_CN", "en_US"]

    for lang in languages:
        ts_file = os.path.join(i18n_dir, f"{lang}.ts")

        cmd = [
            sys.executable, "-m", "pyside6-lupdate",
            "-noobsolete",
            src_dir,
            "-ts", ts_file,
        ]

        print(f"Generating {lang}.ts...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✓ Generated {ts_file}")
            else:
                print(f"  ✗ Failed: {result.stderr}")
        except FileNotFoundError:
            print("  pyside6-lupdate not found. Install PySide6 first.")
            break

    # Compile .ts to .qm files
    for lang in languages:
        ts_file = os.path.join(i18n_dir, f"{lang}.ts")
        qm_file = os.path.join(i18n_dir, f"{lang}.qm")

        if not os.path.exists(ts_file):
            continue

        cmd = [
            sys.executable, "-m", "pyside6-lrelease",
            ts_file,
            "-qm", qm_file,
        ]

        print(f"Compiling {lang}.qm...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✓ Compiled {qm_file}")
            else:
                print(f"  ✗ Failed: {result.stderr}")
        except FileNotFoundError:
            print("  pyside6-lrelease not found. Install PySide6 first.")
            break


if __name__ == "__main__":
    generate_translations()

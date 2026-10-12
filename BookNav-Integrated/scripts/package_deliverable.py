"""
Script to package a clean deliverable of BookNav into BookNav-Integrated/.

Strictly excludes:
- node_modules/
- __pycache__/ and *.pyc
- .pytest_cache/
- client/dist/
- *.log files
- .env files (retains .env.example)
- temporary files
"""

import os
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "BookNav-Integrated"

EXCLUDED_DIRS = {
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    ".git",
    "BookNav-Integrated",
    ".vite",
}

EXCLUDED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
    ".tmp_build",
}

EXCLUDED_FILES = {
    ".env",
    "Thumbs.db",
    ".DS_Store",
}


def should_copy_file(path: Path) -> bool:
    if path.name in EXCLUDED_FILES:
        return False
    if path.name.startswith(".env.") and path.name != ".env.example":
        return False
    if path.suffix in EXCLUDED_EXTENSIONS:
        return False
    return True


def package_project():
    if OUTPUT_DIR.exists():
        print(f"Cleaning existing deliverable directory at {OUTPUT_DIR}...")
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Packaging clean deliverable into: {OUTPUT_DIR}")

    file_count = 0
    dir_count = 0

    for root, dirs, files in os.walk(ROOT_DIR):
        # Prune excluded directories in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".git")]

        rel_root = Path(root).relative_to(ROOT_DIR)
        target_root = OUTPUT_DIR / rel_root
        target_root.mkdir(parents=True, exist_ok=True)
        dir_count += 1

        for f in files:
            src_file = Path(root) / f
            if should_copy_file(src_file):
                dst_file = target_root / f
                shutil.copy2(src_file, dst_file)
                file_count += 1

    print("\n" + "=" * 60)
    print("      BOOKNAV PACKAGING SUMMARY")
    print("=" * 60)
    print(f"Destination:     {OUTPUT_DIR}")
    print(f"Directories:     {dir_count}")
    print(f"Files Copied:    {file_count}")
    print("Exclusions:      node_modules, caches, logs, .env strictly excluded")
    print("============================================================\n")


if __name__ == "__main__":
    package_project()

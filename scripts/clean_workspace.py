import os
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # project root (…/Archaion)
VENVS = {ROOT.parent / ".venv", ROOT / ".venv"}

PATTERNS_FILES = [
    "*.log",
    "*.log.*",
    "*.tmp",
    "*.cache",
]

DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
}

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
}

def should_skip_dir(p: Path) -> bool:
    parts = {part.lower() for part in p.parts}
    if any(ex.lower() in parts for ex in EXCLUDE_DIRS):
        return True
    # skip Python venvs anywhere
    if any(".venv" in part.lower() for part in p.parts):
        return True
    return False

removed_files = []
removed_dirs = []

def remove_file(p: Path):
    try:
        p.unlink(missing_ok=True)
        removed_files.append(str(p))
    except Exception:
        pass

def remove_dir(p: Path):
    try:
        shutil.rmtree(p, ignore_errors=True)
        removed_dirs.append(str(p))
    except Exception:
        pass

def clean_logs_and_caches():
    # 1) Project-known logs directory
    logs_dir = ROOT / "logs"
    if logs_dir.exists() and logs_dir.is_dir():
        for child in logs_dir.rglob("*"):
            if child.is_file():
                remove_file(child)

    # 2) Files by patterns (excluding .venv and node_modules)
    for base in [ROOT, ROOT.parent]:
        for pattern in PATTERNS_FILES:
            for p in base.rglob(pattern):
                if p.is_file() and not should_skip_dir(p.parent):
                    remove_file(p)

    # 3) Cache directories
    for base in [ROOT, ROOT.parent]:
        for d in base.rglob("*"):
            if d.is_dir() and d.name in DIR_NAMES and not should_skip_dir(d):
                remove_dir(d)

if __name__ == "__main__":
    clean_logs_and_caches()
    print("Cleanup complete")
    print(f"Removed files: {len(removed_files)}")
    if removed_files:
        print("\n".join(removed_files[:50]))
        if len(removed_files) > 50:
            print("… (truncated)")
    print(f"Removed directories: {len(removed_dirs)}")
    if removed_dirs:
        print("\n".join(removed_dirs[:50]))
        if len(removed_dirs) > 50:
            print("… (truncated)")

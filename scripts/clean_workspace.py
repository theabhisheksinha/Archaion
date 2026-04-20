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

def iter_dirs_pruned(base: Path):
    for root, dirs, files in os.walk(base, topdown=True):
        # prune excluded dirs in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and ".venv" not in d.lower()]
        yield Path(root), [Path(root) / f for f in files]

def clean_logs_and_caches():
    # 1) Project-known logs directory
    for logs_dir in [ROOT / "logs", ROOT.parent / "logs"]:
        if logs_dir.exists() and logs_dir.is_dir():
            for child in logs_dir.rglob("*"):
                if child.is_file():
                    remove_file(child)

    # 2) Files by patterns (excluding pruned dirs)
    for base in [ROOT, ROOT.parent]:
        for root, files in iter_dirs_pruned(base):
            for f in files:
                if any(f.match(pat) for pat in PATTERNS_FILES):
                    remove_file(f)

    # 3) Cache directories (pruned walk)
    for base in [ROOT, ROOT.parent]:
        for root, _files in iter_dirs_pruned(base):
            for dname in DIR_NAMES:
                d = root / dname
                if d.exists() and d.is_dir():
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

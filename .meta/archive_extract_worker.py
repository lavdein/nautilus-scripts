#!/usr/bin/env python3
"""
Worker: extract archives.
Usage: archive_extract_worker.py progress_file file1 file2 ...
Extracts each archive into a folder next to it.
"""
import sys, subprocess, zipfile, tarfile
from pathlib import Path

progress_file = sys.argv[1]
files         = [f for f in sys.argv[2:] if f]


def write(pct, label, folder=""):
    suffix = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{suffix}")


def unique_dir(p: Path) -> Path:
    if not p.exists():
        return p
    c = 1
    while True:
        candidate = p.parent / f"{p.name}_{c}"
        if not candidate.exists():
            return candidate
        c += 1


def archive_stem(p: Path) -> str:
    name = p.name
    for ext in [".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst"]:
        if name.endswith(ext):
            return name[: -len(ext)]
    return p.stem


total  = len(files)
errors = []
write(0, "Подготовка...")

for i, src in enumerate(files):
    p = Path(src)
    write(i * 100 // total, f"({i+1}/{total}) {p.name}", str(p.parent))

    dest = unique_dir(p.parent / archive_stem(p))
    dest.mkdir(parents=True, exist_ok=True)

    try:
        name_lower = p.name.lower()
        if name_lower.endswith(".zip"):
            with zipfile.ZipFile(p) as z:
                z.extractall(dest)
        elif any(name_lower.endswith(s) for s in [".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".tar"]):
            with tarfile.open(p) as t:
                t.extractall(dest)
        else:
            # fallback: try system tar/unzip
            result = subprocess.run(["tar", "-xf", str(p), "-C", str(dest)], capture_output=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode())

        write((i + 1) * 100 // total, f"✓ {p.name}", str(dest))
    except Exception as e:
        errors.append(f"{p.name}: {e}")
        try:
            dest.rmdir()
        except OSError:
            pass

if errors:
    body = "Не удалось распаковать:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "Архив", body, "-i", "dialog-warning"])
    write(100, f"Ошибок: {len(errors)}")
else:
    all_dirs = list(dict.fromkeys(str(Path(f).parent) for f in files))
    Path(progress_file).write_text(
        f"DONE|Распаковано: {total} архив(ов)|{':'.join(all_dirs)}"
    )

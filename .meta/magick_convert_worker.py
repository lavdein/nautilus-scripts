#!/usr/bin/env python3
"""
Worker: convert images to another format via ImageMagick.
Usage: magick_convert_worker.py progress_file format quality file1 file2 ...
quality: "" (none), "lossless" (webp), or number string like "85"
"""
import sys, subprocess
from pathlib import Path

progress_file = sys.argv[1]
fmt           = sys.argv[2]
quality       = sys.argv[3]
files         = sys.argv[4:]


def write(pct, label, folder=""):
    suffix = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{suffix}")


def quality_args():
    if not quality:
        return []
    if quality == "lossless":
        return ["-define", "webp:lossless=true"]
    return ["-quality", quality]


total  = len(files)
errors = []
write(0, "Подготовка...")

for i, src in enumerate(files):
    name   = Path(src).name
    parent = Path(src).parent
    stem   = Path(src).stem

    dst = parent / f"{stem}.{fmt}"
    c = 1
    while dst.exists():
        dst = parent / f"{stem}_{c}.{fmt}"
        c += 1

    write(i * 100 // total, f"({i+1}/{total}) {name}", str(parent))

    result = subprocess.run(
        ["magick", src] + quality_args() + [str(dst)],
        capture_output=True,
    )

    if result.returncode != 0:
        errors.append(name)
        dst.unlink(missing_ok=True)
    else:
        write((i + 1) * 100 // total, f"✓ {name}", str(parent))

if errors:
    body = "Не удалось конвертировать:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "Конвертировать в формат", body, "-i", "dialog-warning"])
    write(100, f"Ошибок: {len(errors)}")
else:
    all_dirs = list(dict.fromkeys(str(Path(f).parent) for f in files))
    Path(progress_file).write_text(
        f"DONE|Готово: {total} файл(ов) → {fmt.upper()}|{':'.join(all_dirs)}"
    )

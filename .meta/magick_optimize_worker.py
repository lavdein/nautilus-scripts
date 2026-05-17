#!/usr/bin/env python3
"""
Worker: optimize images via ImageMagick (strip metadata, recompress).
Usage: magick_optimize_worker.py progress_file file1 file2 ...
"""
import sys, subprocess
from pathlib import Path

progress_file = sys.argv[1]
files         = [f for f in sys.argv[2:] if f]


def write(pct, label, folder=""):
    suffix = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{suffix}")


total  = len(files)
errors = []
write(0, "Подготовка...")

for i, src in enumerate(files):
    p      = Path(src)
    parent = p.parent
    stem   = p.stem
    ext    = p.suffix

    dst = parent / f"{stem}_opt{ext}"
    c = 1
    while dst.exists():
        dst = parent / f"{stem}_opt_{c}{ext}"
        c += 1

    write(i * 100 // total, f"({i+1}/{total}) {p.name}", str(parent))

    result = subprocess.run(
        ["magick", src, "-strip", str(dst)],
        capture_output=True,
    )

    if result.returncode != 0:
        errors.append(p.name)
        dst.unlink(missing_ok=True)
    else:
        before = p.stat().st_size
        after  = dst.stat().st_size
        saved  = max(0, (before - after) * 100 // before)
        write((i + 1) * 100 // total, f"✓ {p.name} (−{saved}%)", str(parent))

if errors:
    body = "Не удалось оптимизировать:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "Изображения", body, "-i", "dialog-warning"])
    write(100, f"Ошибок: {len(errors)}")
else:
    all_dirs = list(dict.fromkeys(str(Path(f).parent) for f in files))
    Path(progress_file).write_text(
        f"DONE|Оптимизировано: {total} файл(ов)|{':'.join(all_dirs)}"
    )

#!/usr/bin/env python3
"""
Worker: resize images via ImageMagick.
Usage: magick_resize_worker.py progress_file resize_arg suffix file1 file2 ...
resize_arg: "50%", "1920x", "x1080", "1920x1080"
suffix:     "_50pct", "_w1920", "_h1080", "_1920_1080"
"""
import sys, subprocess
from pathlib import Path

progress_file = sys.argv[1]
resize_arg    = sys.argv[2]
suffix        = sys.argv[3]
files         = sys.argv[4:]


def write(pct, label, folder=""):
    sfx = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{sfx}")


total  = len(files)
errors = []
write(0, "Подготовка...")

for i, src in enumerate(files):
    name   = Path(src).name
    parent = Path(src).parent
    stem   = Path(src).stem
    ext    = Path(src).suffix

    dst = parent / f"{stem}{suffix}{ext}"
    c = 1
    while dst.exists():
        dst = parent / f"{stem}{suffix}_{c}{ext}"
        c += 1

    write(i * 100 // total, f"({i+1}/{total}) {name}", str(parent))

    result = subprocess.run(
        ["magick", src, "-resize", resize_arg, str(dst)],
        capture_output=True,
    )

    if result.returncode != 0:
        errors.append(name)
        dst.unlink(missing_ok=True)
    else:
        write((i + 1) * 100 // total, f"✓ {name}", str(parent))

if errors:
    body = "Не удалось обработать:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "Изменить размер", body, "-i", "dialog-warning"])
    write(100, f"Ошибок: {len(errors)}")
else:
    all_dirs = list(dict.fromkeys(str(Path(f).parent) for f in files))
    Path(progress_file).write_text(
        f"DONE|Готово: {total} файл(ов)|{':'.join(all_dirs)}"
    )

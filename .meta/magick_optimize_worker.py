#!/usr/bin/env python3
"""
Worker: optimize images via ImageMagick.
Usage: magick_optimize_worker.py progress_file strip quality file1 file2 ...
strip:   "Убрать EXIF" | "Сохранить"
quality: "" (auto per-format) | number string like "85"
"""
import sys, subprocess
from pathlib import Path

progress_file = sys.argv[1]
strip_meta    = sys.argv[2]
quality       = sys.argv[3]
files         = [f for f in sys.argv[4:] if f]


def write(pct, label, folder=""):
    suffix = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{suffix}")


def orig_jpeg_quality(src):
    r = subprocess.run(
        ["magick", "identify", "-format", "%Q", src],
        capture_output=True, text=True,
    )
    try:
        return int(r.stdout.strip())
    except Exception:
        return 85


def build_args(src, dst):
    ext = Path(src).suffix.lower()
    args = ["magick", src]

    if strip_meta == "Убрать EXIF":
        args += ["-strip"]

    if quality:
        # Explicit quality chosen by user
        args += ["-quality", quality]
    elif ext in (".jpg", ".jpeg"):
        # Auto: read original quality, cap at 82 to guarantee reduction
        q = min(orig_jpeg_quality(src), 82)
        args += ["-quality", str(q)]
    elif ext == ".png":
        # Lossless: maximum zlib compression level
        args += ["-define", "png:compression-level=9",
                 "-define", "png:compression-filter=5"]
    elif ext == ".webp":
        args += ["-quality", "80"]
    # Other formats: rely on -strip alone

    args.append(str(dst))
    return args


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

    result = subprocess.run(build_args(src, dst), capture_output=True)

    if result.returncode != 0:
        errors.append(p.name)
        dst.unlink(missing_ok=True)
    else:
        before = p.stat().st_size
        after  = dst.stat().st_size
        if after >= before:
            # Recompression made it bigger — keep original, discard output
            dst.unlink(missing_ok=True)
            dst = parent / f"{stem}_opt{ext}"
            import shutil
            shutil.copy2(src, dst)
            write((i + 1) * 100 // total, f"✓ {p.name} (уже оптимально)", str(parent))
        else:
            saved = (before - after) * 100 // before
            write((i + 1) * 100 // total, f"✓ {p.name} (−{saved}%)", str(parent))

if errors:
    body = "Не удалось оптимизировать:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "Обработать изображения", body, "-i", "dialog-warning"])
    write(100, f"Ошибок: {len(errors)}")
else:
    all_dirs = list(dict.fromkeys(str(Path(f).parent) for f in files))
    Path(progress_file).write_text(
        f"DONE|Оптимизировано: {total} файл(ов)|{':'.join(all_dirs)}"
    )

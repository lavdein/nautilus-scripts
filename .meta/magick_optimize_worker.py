#!/usr/bin/env python3
"""
Worker: optimize images via ImageMagick (JPEG/WebP) and oxipng/optipng (PNG).
Usage: magick_optimize_worker.py progress_file strip quality file1 file2 ...
strip:   "Убрать EXIF" | "Сохранить"
quality: "" (auto per-format) | number string like "85"
"""
import sys, subprocess, shutil
from pathlib import Path

progress_file = sys.argv[1]
strip_meta    = sys.argv[2]
quality       = sys.argv[3]
files         = [f for f in sys.argv[4:] if f]

PNG_TOOL = (
    "oxipng"  if shutil.which("oxipng")  else
    "optipng" if shutil.which("optipng") else
    None
)


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


def build_args_png(src, dst):
    do_strip = strip_meta == "Убрать EXIF"
    if PNG_TOOL == "oxipng":
        args = ["oxipng", "--opt", "4", "--out", str(dst)]
        if do_strip:
            args += ["--strip", "all"]
        args.append(src)
        return args
    elif PNG_TOOL == "optipng":
        args = ["optipng", "-o5", "-quiet", "-out", str(dst)]
        if do_strip:
            args += ["-strip", "all"]
        args.append(src)
        return args
    return None  # no tool available


def build_args(src, dst):
    ext = Path(src).suffix.lower()
    args = ["magick", src]

    if strip_meta == "Убрать EXIF":
        args += ["-strip"]

    if quality:
        args += ["-quality", quality]
    elif ext in (".jpg", ".jpeg"):
        q = min(orig_jpeg_quality(src), 82)
        args += ["-quality", str(q)]
    elif ext == ".webp":
        args += ["-quality", "80"]

    args.append(str(dst))
    return args


total  = len(files)
errors = []
write(0, "Подготовка...")

png_files = [f for f in files if Path(f).suffix.lower() == ".png"]
if png_files and PNG_TOOL is None:
    subprocess.run(["notify-send", "--app-name", "Обработать изображения",
                    "Обработать изображения",
                    "Для сжатия PNG установите oxipng или optipng:\nsudo dnf install oxipng"])

for i, src in enumerate(files):
    p      = Path(src)
    parent = p.parent
    ext    = p.suffix.lower()

    dst = parent / f"{p.stem}_opt{p.suffix}"
    c = 1
    while dst.exists():
        dst = parent / f"{p.stem}_opt_{c}{p.suffix}"
        c += 1

    write(i * 100 // total, f"({i+1}/{total}) {p.name}", str(parent))

    if ext == ".png":
        cmd = build_args_png(src, dst)
        if cmd is None:
            errors.append(f"{p.name}: нет oxipng/optipng")
            continue
    else:
        cmd = build_args(src, dst)

    result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0:
        errors.append(p.name)
        dst.unlink(missing_ok=True)
        continue

    if not dst.exists():
        # oxipng/optipng may skip writing if file can't be reduced
        write((i + 1) * 100 // total, f"✓ {p.name} (уже оптимально)", str(parent))
        continue

    before = p.stat().st_size
    after  = dst.stat().st_size

    if after >= before:
        dst.unlink(missing_ok=True)
        import shutil as _sh
        _sh.copy2(src, dst)
        write((i + 1) * 100 // total, f"✓ {p.name} (уже оптимально)", str(parent))
    else:
        saved = (before - after) * 100 // before
        write((i + 1) * 100 // total, f"✓ {p.name} (−{saved}%)", str(parent))

if errors:
    body = "Не удалось оптимизировать:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "--app-name", "Обработать изображения", "Обработать изображения", body])
    write(100, f"Ошибок: {len(errors)}")
else:
    all_dirs = list(dict.fromkeys(str(Path(f).parent) for f in files))
    Path(progress_file).write_text(
        f"DONE|Оптимизировано: {total} файл(ов)|{':'.join(all_dirs)}"
    )

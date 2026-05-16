#!/usr/bin/env python3
"""
Worker: extract frame sequence from video files.
Usage: ffmpeg_extract_worker.py progress_file fps_val fmt file1 file2 ...
fps_val: empty string = all frames, otherwise "1", "2", "5", "10"
fmt: png | jpg | webp
"""
import sys, subprocess, json, time, tempfile, os
from pathlib import Path

progress_file = sys.argv[1]
fps_val       = sys.argv[2]
fmt           = sys.argv[3]
files         = sys.argv[4:]


def write(pct, label, folder=""):
    suffix = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{suffix}")


def get_duration_us(path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True, text=True, timeout=10,
        )
        return int(float(json.loads(r.stdout)["format"]["duration"]) * 1_000_000)
    except Exception:
        return 0


total  = len(files)
errors = []
all_dirs = []
write(0, "Подготовка...")

for i, src in enumerate(files):
    name   = Path(src).name
    parent = Path(src).parent
    stem   = Path(src).stem

    out_dir = parent / f"{stem}_кадры"
    c = 1
    while out_dir.exists():
        out_dir = parent / f"{stem}_кадры_{c}"
        c += 1
    out_dir.mkdir()
    all_dirs.append(str(out_dir))

    dur_us = get_duration_us(src)
    write(i * 100 // total, f"({i+1}/{total}) {name}", str(out_dir))

    cmd = ["ffmpeg", "-y", "-i", src]
    if fps_val:
        cmd += ["-vf", f"fps={fps_val}"]

    prog_tmp   = tempfile.mktemp(prefix="ffext_")
    stderr_tmp = tempfile.mktemp(prefix="ffext_err_")
    cmd += ["-progress", prog_tmp, str(out_dir / f"frame_%06d.{fmt}")]

    proc = subprocess.Popen(cmd, stderr=open(stderr_tmp, "w"))

    while proc.poll() is None:
        time.sleep(0.25)
        try:
            for line in reversed(Path(prog_tmp).read_text().splitlines()):
                if line.startswith("out_time_us="):
                    us = int(line.split("=")[1])
                    if dur_us > 0:
                        file_pct = min(99, us * 100 // dur_us)
                        write((i * 100 + file_pct) // total,
                              f"({i+1}/{total}) {name}", str(out_dir))
                    break
        except Exception:
            pass

    for tmp in (prog_tmp, stderr_tmp):
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass

    if proc.returncode != 0:
        errors.append(name)
    else:
        n = len(list(out_dir.glob(f"*.{fmt}")))
        write((i + 1) * 100 // total, f"✓ {name} — {n} кадров", str(out_dir))

if errors:
    body = "Не удалось обработать:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "Видео в секвенцию", body, "-i", "dialog-warning"])
    write(100, f"Ошибок: {len(errors)}")
else:
    Path(progress_file).write_text(
        f"DONE|Готово: {total} файл(ов)|{':'.join(all_dirs)}"
    )

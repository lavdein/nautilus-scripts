#!/usr/bin/env python3
"""
ffmpeg remux worker — runs in background, reports progress to indicator.py.
Usage: ffmpeg_remux_worker.py progress_file format file1 file2 ...
Progress protocol: "pct|label"  →  indicator shows percentage
                   "DONE|msg"   →  indicator shows ✓ and exits
"""
import sys, subprocess, json, time, tempfile, os
from pathlib import Path

progress_file = sys.argv[1]
fmt           = sys.argv[2]
files         = sys.argv[3:]


def write(pct, label):
    Path(progress_file).write_text(f"{pct}|{label}")


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

    dur_us = get_duration_us(src)
    write(i * 100 // total, f"({i+1}/{total}) {name}")

    prog_tmp = tempfile.mktemp(prefix="ffremux_")
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-i", src,
         "-map", "0", "-map", "-0:d",   # drop incompatible data streams
         "-c", "copy",
         "-progress", prog_tmp, str(dst)],
        stderr=subprocess.PIPE,
    )

    while proc.poll() is None:
        time.sleep(0.25)
        try:
            for line in reversed(Path(prog_tmp).read_text().splitlines()):
                if line.startswith("out_time_us="):
                    us = int(line.split("=")[1])
                    if dur_us > 0:
                        file_pct = min(99, us * 100 // dur_us)
                        write((i * 100 + file_pct) // total, f"({i+1}/{total}) {name}")
                    break
        except Exception:
            pass

    try:
        os.unlink(prog_tmp)
    except FileNotFoundError:
        pass

    if proc.returncode != 0:
        errors.append(name)
        dst.unlink(missing_ok=True)

# Finish
if errors:
    body = "Не удалось перепаковать:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "Сменить контейнер", body, "-i", "dialog-warning"])
    write(100, f"Ошибок: {len(errors)}")
else:
    Path(progress_file).write_text(f"DONE|Готово: {total} файл(ов) → {fmt.upper()}")

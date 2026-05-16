#!/usr/bin/env python3
"""
Worker: extract audio from video files.
Usage: ffmpeg_audio_worker.py progress_file format file1 file2 ...
format: mp3 | aac | flac | ogg | wav
"""
import sys, subprocess, json, time, tempfile, os
from pathlib import Path

progress_file = sys.argv[1]
fmt           = sys.argv[2]
files         = sys.argv[3:]

CODEC_ARGS = {
    "mp3":  ["-c:a", "libmp3lame", "-q:a", "2"],
    "aac":  ["-c:a", "aac", "-b:a", "192k"],
    "flac": ["-c:a", "flac"],
    "ogg":  ["-c:a", "libvorbis", "-q:a", "6"],
    "wav":  ["-c:a", "pcm_s16le"],
}


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
    write(i * 100 // total, f"({i+1}/{total}) {name}", str(parent))

    prog_tmp   = tempfile.mktemp(prefix="ffaudio_")
    stderr_tmp = tempfile.mktemp(prefix="ffaudio_err_")

    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-i", src, "-vn"] + CODEC_ARGS[fmt]
        + ["-progress", prog_tmp, str(dst)],
        stderr=open(stderr_tmp, "w"),
    )

    while proc.poll() is None:
        time.sleep(0.25)
        try:
            for line in reversed(Path(prog_tmp).read_text().splitlines()):
                if line.startswith("out_time_us="):
                    us = int(line.split("=")[1])
                    if dur_us > 0:
                        file_pct = min(99, us * 100 // dur_us)
                        write((i * 100 + file_pct) // total,
                              f"({i+1}/{total}) {name}", str(parent))
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
        dst.unlink(missing_ok=True)
    else:
        write((i + 1) * 100 // total, f"✓ {name}", str(parent))

if errors:
    body = "Не удалось обработать:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "Извлечь звук", body, "-i", "dialog-warning"])
    write(100, f"Ошибок: {len(errors)}")
else:
    all_dirs = list(dict.fromkeys(str(Path(f).parent) for f in files))
    Path(progress_file).write_text(
        f"DONE|Готово: {total} файл(ов) → {fmt.upper()}|{':'.join(all_dirs)}"
    )

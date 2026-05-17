#!/usr/bin/env python3
"""
ffmpeg remux worker — runs in background, reports progress to indicator.py.
Usage: ffmpeg_remux_worker.py progress_file format file1 file2 ...
"""
import sys, subprocess, json, time, tempfile, os
from pathlib import Path

progress_file = sys.argv[1]
fmt           = sys.argv[2]
files         = [f for f in sys.argv[3:] if f]

# Codecs that need to be transcoded for each container
# (MKV supports everything, so it's not here)
INCOMPATIBLE_AUDIO = {
    "mp4": {"opus", "vorbis", "flac"},
    "mov": {"opus", "vorbis", "flac"},
    "avi": {"opus", "vorbis", "flac"},
}

AUDIO_FALLBACK = {
    "mp4": ["-c:a", "aac", "-b:a", "192k"],
    "mov": ["-c:a", "aac", "-b:a", "192k"],
    "avi": ["-c:a", "libmp3lame", "-q:a", "2"],
}


def write(pct, label, folder=""):
    suffix = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{suffix}")


def probe(path):
    """Returns (duration_us, audio_codec) for a file."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(r.stdout)
        dur_us = int(float(data["format"]["duration"]) * 1_000_000)
        audio = next(
            (s.get("codec_name", "") for s in data.get("streams", [])
             if s["codec_type"] == "audio"),
            "",
        )
        return dur_us, audio
    except Exception:
        return 0, ""


total  = len(files)
errors = []
transcoded_files = 0
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

    dur_us, audio_codec = probe(src)
    write(i * 100 // total, f"({i+1}/{total}) {name}", str(parent))

    # Decide audio handling
    need_transcode = audio_codec in INCOMPATIBLE_AUDIO.get(fmt, set())
    if need_transcode:
        audio_args = AUDIO_FALLBACK[fmt]
        map_args   = ["-map", "0:v", "-map", "0:a"]
        video_args = ["-c:v", "copy"]
    elif fmt == "mkv":
        audio_args = ["-c:a", "copy"]
        map_args   = ["-map", "0"]
        video_args = ["-c:v", "copy"]
    else:
        audio_args = ["-c:a", "copy"]
        map_args   = ["-map", "0:v", "-map", "0:a"]
        video_args = ["-c:v", "copy"]

    prog_tmp   = tempfile.mktemp(prefix="ffremux_")
    stderr_tmp = tempfile.mktemp(prefix="ffremux_err_")

    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-i", src]
        + map_args + video_args + audio_args
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
                        write((i * 100 + file_pct) // total, f"({i+1}/{total}) {name}", str(parent))
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
    elif need_transcode:
        transcoded_files += 1

# Notification + done signal
if errors:
    body = "Не удалось перепаковать:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "Сменить контейнер", body, "-i", "dialog-warning"])
    write(100, f"Ошибок: {len(errors)}")
else:
    note      = f" (аудио → {'AAC' if fmt != 'avi' else 'MP3'})" if transcoded_files else ""
    all_dirs  = list(dict.fromkeys(str(Path(f).parent) for f in files))
    Path(progress_file).write_text(
        f"DONE|Готово: {total} файл(ов) → {fmt.upper()}{note}|{':'.join(all_dirs)}"
    )

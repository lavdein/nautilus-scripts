#!/usr/bin/env python3
"""
Worker: assemble video from image sequence.
Usage: ffmpeg_sequence_worker.py progress_file fps fmt img1 img2 ...
Files are sorted alphabetically before encoding.
"""
import sys, subprocess, time, tempfile, os
from pathlib import Path

progress_file = sys.argv[1]
fps           = sys.argv[2]
fmt           = sys.argv[3]
files         = sorted(sys.argv[4:])

total_frames = len(files)
parent = Path(files[0]).parent


def write(pct, label, folder=""):
    suffix = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{suffix}")


write(0, f"Подготовка {total_frames} кадров...", str(parent))

# Output file — named after parent folder
stem = parent.name or "sequence"
dst = parent / f"{stem}.{fmt}"
c = 1
while dst.exists():
    dst = parent / f"{stem}_{c}.{fmt}"
    c += 1

# Filelist for ffmpeg concat
filelist   = tempfile.mktemp(prefix="ffseq_list_", suffix=".txt")
prog_tmp   = tempfile.mktemp(prefix="ffseq_")
stderr_tmp = tempfile.mktemp(prefix="ffseq_err_")

with open(filelist, "w") as f:
    for img in files:
        f.write(f"file '{img}'\n")

crf = "18" if fmt == "mp4" else "15"

proc = subprocess.Popen(
    ["ffmpeg", "-y",
     "-f", "concat", "-safe", "0", "-i", filelist,
     "-r", fps,
     "-c:v", "libx264", "-crf", crf, "-pix_fmt", "yuv420p",
     "-progress", prog_tmp, str(dst)],
    stderr=open(stderr_tmp, "w"),
)

while proc.poll() is None:
    time.sleep(0.25)
    try:
        for line in reversed(Path(prog_tmp).read_text().splitlines()):
            if line.startswith("frame="):
                frame = int(line.split("=")[1])
                pct = min(99, frame * 100 // total_frames)
                write(pct, f"{frame}/{total_frames} кадров → {dst.name}", str(parent))
                break
    except Exception:
        pass

for tmp in (filelist, prog_tmp, stderr_tmp):
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass

if proc.returncode != 0:
    subprocess.run(["notify-send", "Секвенция в видео",
                    "Ошибка сборки. Проверьте что все изображения одного размера.",
                    "-i", "dialog-warning"])
    write(100, "Ошибка")
else:
    Path(progress_file).write_text(f"DONE|Готово: {dst.name}|{str(parent)}")

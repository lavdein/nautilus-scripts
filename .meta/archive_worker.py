#!/usr/bin/env python3
"""
Worker: create zip/tar.gz/tar.xz archive.
Usage: archive_worker.py progress_file archive_path format name1 name2 ...
Runs from the parent directory of the files.
"""
import sys, subprocess, os
from pathlib import Path

progress_file = sys.argv[1]
archive_path  = sys.argv[2]
fmt           = sys.argv[3]
names         = sys.argv[4:]
parent        = Path(archive_path).parent


def write(pct, label, folder=""):
    suffix = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{suffix}")


write(0, f"Создаётся {Path(archive_path).name}...", str(parent))

os.chdir(parent)

if fmt == "zip":
    cmd = ["zip", "-r", archive_path] + names
elif fmt == "tar.gz":
    cmd = ["tar", "-czf", archive_path] + names
elif fmt == "tar.xz":
    cmd = ["tar", "-cJf", archive_path] + names

result = subprocess.run(cmd, capture_output=True)

if result.returncode != 0:
    subprocess.run(["notify-send", "Создать архив",
                    "Не удалось создать архив.", "-i", "dialog-warning"])
    write(100, "Ошибка")
else:
    size = subprocess.run(["du", "-sh", archive_path],
                          capture_output=True, text=True).stdout.split()[0]
    Path(progress_file).write_text(
        f"DONE|{Path(archive_path).name}  ({size})|{str(parent)}"
    )

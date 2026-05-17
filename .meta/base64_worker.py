#!/usr/bin/env python3
"""
Worker: encode/decode files to/from Base64.
Usage: base64_worker.py "Кодировать в Base64"|"Декодировать из Base64" file1 file2 ...
"""
import sys, base64, subprocess
from pathlib import Path

mode  = sys.argv[1]
files = [f for f in sys.argv[2:] if f]
done  = []
errors = []


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    c = 1
    while True:
        candidate = p.parent / f"{p.stem}_{c}{p.suffix}"
        if not candidate.exists():
            return candidate
        c += 1


for src in files:
    p = Path(src)
    try:
        if mode == "Кодировать в Base64":
            data = base64.b64encode(p.read_bytes()).decode() + '\n'
            out  = unique_path(p.parent / (p.name + '.b64'))
            out.write_text(data)
        else:
            raw = base64.b64decode(p.read_text().strip())
            out = unique_path(p.parent / p.stem)
            out.write_bytes(raw)
        done.append(p.name)
    except Exception as e:
        errors.append(f"{p.name}: {e}")

verb = "Закодировано" if mode == "Кодировать в Base64" else "Декодировано"
msg  = f"{verb}: {len(done)} файл(ов)"

if errors:
    err_body = msg + "\nОшибки:\n" + "\n".join(f"• {e}" for e in errors)
    subprocess.run(["notify-send", "--app-name", "Base64", "Base64", err_body])
else:
    subprocess.run(["notify-send", "--app-name", "Base64", "Base64", msg])

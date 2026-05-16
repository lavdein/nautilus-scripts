#!/usr/bin/env python3
import sys, json, time, subprocess
from pathlib import Path
from faster_whisper import WhisperModel

progress_file = sys.argv[1]
model_id      = sys.argv[2]
lang          = None if sys.argv[3] == "auto" else sys.argv[3]
do_txt        = sys.argv[4] == "true"
do_srt        = sys.argv[5] == "true"
files         = sys.argv[6:]
total         = len(files)

MODELS_DIR = str(Path(__file__).parent / "models")


def set_progress(pct, label, folder=""):
    suffix = f"|{folder}" if folder else ""
    open(progress_file, "w").write(f"{pct}|{label}{suffix}")


def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


def fmt_ts(t):
    h, rem = divmod(t, 3600)
    m, s   = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


set_progress(0, "Загрузка модели...")

try:
    model  = WhisperModel(model_id, device="cuda", compute_type="float16", download_root=MODELS_DIR)
    device = "GPU"
except Exception:
    model  = WhisperModel(model_id, device="cpu", compute_type="int8", download_root=MODELS_DIR)
    device = "CPU"

UPDATE_INTERVAL = 1.5

for idx, file_path in enumerate(files):
    path     = Path(file_path)
    out      = path.parent / path.stem
    name     = path.name
    base_pct = idx * 100 // total

    set_progress(base_pct, f"[{device}] {name}", str(path.parent))

    try:
        duration = get_duration(file_path)
    except Exception:
        duration = None

    segments_gen, _ = model.transcribe(
        file_path,
        language=lang,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    txt_parts, srt_parts = [], []
    last_update = 0.0
    seg_num = 0

    for seg in segments_gen:
        seg_num += 1
        txt_parts.append(seg.text.strip())
        if do_srt:
            srt_parts.append(
                f"{seg_num}\n{fmt_ts(seg.start)} --> {fmt_ts(seg.end)}\n{seg.text.strip()}\n"
            )

        now = time.monotonic()
        if duration and now - last_update >= UPDATE_INTERVAL:
            seg_pct   = seg.end / duration
            total_pct = int((idx + seg_pct) * 100 / total)
            set_progress(total_pct, f"[{device}] {name}  {int(seg_pct * 100)}%", str(path.parent))
            last_update = now

    if do_txt:
        (out.parent / (out.name + ".txt")).write_text("\n".join(txt_parts), encoding="utf-8")
    if do_srt:
        (out.parent / (out.name + ".srt")).write_text("\n".join(srt_parts), encoding="utf-8")

    set_progress((idx + 1) * 100 // total, f"✓ {name}")

all_dirs = list(dict.fromkeys(str(Path(f).parent) for f in files))
open(progress_file, "w").write(f"DONE|Готово — {total} файл(ов)|{':'.join(all_dirs)}")

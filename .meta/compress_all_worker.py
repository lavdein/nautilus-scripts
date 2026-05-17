#!/usr/bin/env python3
"""
Universal file compression worker.
Usage: compress_all_worker.py progress_file preset file1 file2 ...
preset: "Осторожно" | "Баланс" | "Агрессивно"
Output: <stem>_c.<ext> next to original (skipped if result is not smaller).
"""
import sys, json, subprocess, shutil, tempfile, os
from pathlib import Path

progress_file = sys.argv[1]
preset        = sys.argv[2]
files         = [f for f in sys.argv[3:] if f]

# ── Preset settings ───────────────────────────────────────────────────────────
P = {
    "Осторожно":  {"jpg": 88, "webp": 83, "png": 2, "crf": 24, "speed": "slow",  "audio": 192, "pdf": "/printer"},
    "Баланс":     {"jpg": 82, "webp": 75, "png": 4, "crf": 28, "speed": "medium","audio": 128, "pdf": "/ebook"},
    "Агрессивно": {"jpg": 70, "webp": 60, "png": 6, "crf": 32, "speed": "fast",  "audio":  96, "pdf": "/screen"},
}[preset]

HAS_OXIPNG   = shutil.which("oxipng")
HAS_OPTIPNG  = shutil.which("optipng")
HAS_GIFSICLE = shutil.which("gifsicle")
HAS_GS       = shutil.which("gs")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
AUDIO_EXT = {".mp3", ".aac", ".m4a", ".ogg", ".opus", ".wma"}
LOSSLESS_AUDIO = {".flac", ".wav", ".aiff"}
PDF_EXT   = {".pdf"}


def write(pct, label, folder=""):
    sfx = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{sfx}")


def unique_dst(p: Path, suffix="_c") -> Path:
    dst = p.parent / f"{p.stem}{suffix}{p.suffix}"
    c = 1
    while dst.exists():
        dst = p.parent / f"{p.stem}{suffix}_{c}{p.suffix}"
        c += 1
    return dst


def probe_bitrate(src) -> int:
    """Return file bitrate in kbps, 0 on failure."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", src],
            capture_output=True,
        )
        return int(json.loads(r.stdout).get("format", {}).get("bit_rate", 0)) // 1000
    except Exception:
        return 0


def orig_jpeg_quality(src) -> int:
    r = subprocess.run(["magick", "identify", "-format", "%Q", src],
                       capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except Exception:
        return 85


def compress_image(src: Path, dst: Path) -> subprocess.CompletedProcess:
    ext = src.suffix.lower()

    if ext == ".png":
        if HAS_OXIPNG:
            return subprocess.run(
                ["oxipng", "--opt", str(P["png"]), "--strip", "all", "--out", str(dst), str(src)],
                capture_output=True,
            )
        elif HAS_OPTIPNG:
            return subprocess.run(
                ["optipng", f"-o{P['png']}", "-strip", "all", "-quiet", "-out", str(dst), str(src)],
                capture_output=True,
            )
        else:
            return None  # no PNG tool

    elif ext in (".jpg", ".jpeg"):
        q = min(orig_jpeg_quality(str(src)), P["jpg"])
        return subprocess.run(
            ["magick", str(src), "-strip", "-quality", str(q), str(dst)],
            capture_output=True,
        )

    elif ext == ".webp":
        return subprocess.run(
            ["magick", str(src), "-strip", "-quality", str(P["webp"]), str(dst)],
            capture_output=True,
        )

    elif ext == ".gif":
        if HAS_GIFSICLE:
            return subprocess.run(
                ["gifsicle", "-O3", "--colors", "256", str(src), "-o", str(dst)],
                capture_output=True,
            )
        else:
            return None  # no GIF tool


def compress_video(src: Path, dst: Path) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tmp:
        stderr_path = tmp.name
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src),
             "-c:v", "libx264", "-crf", str(P["crf"]), "-preset", P["speed"],
             "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart",
             str(dst)],
            stderr=open(stderr_path, "w"),
            stdout=subprocess.DEVNULL,
        )
    finally:
        os.unlink(stderr_path)
    return result


def compress_audio(src: Path, dst: Path) -> subprocess.CompletedProcess | None:
    current_kbps = probe_bitrate(str(src))
    if current_kbps and current_kbps <= P["audio"]:
        return None  # already at or below target — skip

    ext = src.suffix.lower()
    codec_map = {".mp3": ("libmp3lame", []), ".aac": ("aac", []),
                 ".m4a": ("aac", []), ".ogg": ("libvorbis", []),
                 ".opus": ("libopus", []), ".wma": ("wmav2", [])}
    codec, extra = codec_map.get(ext, ("libopus", []))

    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tmp:
        stderr_path = tmp.name
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src),
             "-c:a", codec, "-b:a", f"{P['audio']}k"] + extra + [str(dst)],
            stderr=open(stderr_path, "w"),
            stdout=subprocess.DEVNULL,
        )
    finally:
        os.unlink(stderr_path)
    return result


def compress_pdf(src: Path, dst: Path) -> subprocess.CompletedProcess | None:
    if not HAS_GS:
        return None
    return subprocess.run(
        ["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5",
         f"-dPDFSETTINGS={P['pdf']}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
         f"-sOutputFile={dst}", str(src)],
        capture_output=True,
    )


# ── Main loop ─────────────────────────────────────────────────────────────────
total   = len(files)
results = {"ok": 0, "skip": 0, "err": 0}
write(0, "Подготовка...")

for i, src_str in enumerate(files):
    src = Path(src_str)
    ext = src.suffix.lower()
    write(i * 100 // total, f"({i+1}/{total}) {src.name}", str(src.parent))

    # Lossless audio — skip
    if ext in LOSSLESS_AUDIO:
        write(i * 100 // total, f"— {src.name} (lossless, пропущено)", str(src.parent))
        results["skip"] += 1
        continue

    dst = unique_dst(src)

    # Choose compressor
    if ext in IMAGE_EXT:
        result = compress_image(src, dst)
    elif ext in VIDEO_EXT:
        result = compress_video(src, dst)
    elif ext in AUDIO_EXT:
        result = compress_audio(src, dst)
        if result is None:
            write((i+1)*100//total, f"— {src.name} (уже сжато)", str(src.parent))
            results["skip"] += 1
            continue
    elif ext in PDF_EXT:
        result = compress_pdf(src, dst)
    else:
        write((i+1)*100//total, f"— {src.name} (формат не поддерживается)", str(src.parent))
        results["skip"] += 1
        continue

    if result is None:
        write((i+1)*100//total, f"— {src.name} (нет инструмента)", str(src.parent))
        results["skip"] += 1
        continue

    if result.returncode != 0:
        dst.unlink(missing_ok=True)
        results["err"] += 1
        continue

    if not dst.exists() or dst.stat().st_size >= src.stat().st_size:
        dst.unlink(missing_ok=True)
        write((i+1)*100//total, f"— {src.name} (уже оптимально)", str(src.parent))
        results["skip"] += 1
        continue

    saved = (src.stat().st_size - dst.stat().st_size) * 100 // src.stat().st_size
    write((i+1)*100//total, f"✓ {src.name} (−{saved}%)", str(src.parent))
    results["ok"] += 1

# ── Finish ────────────────────────────────────────────────────────────────────
parts = []
if results["ok"]:   parts.append(f"Сжато: {results['ok']}")
if results["skip"]: parts.append(f"Пропущено: {results['skip']}")
msg = ", ".join(parts) or "Нечего сжимать"

if results["err"]:
    subprocess.run(["notify-send", "Сжать", f"{msg}\nОшибок: {results['err']}", "-i", "dialog-warning"])
    write(100, f"Ошибок: {results['err']}")
else:
    all_dirs = list(dict.fromkeys(str(Path(f).parent) for f in files))
    Path(progress_file).write_text(f"DONE|{msg}|{':'.join(all_dirs)}")

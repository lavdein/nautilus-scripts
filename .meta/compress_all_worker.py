#!/usr/bin/env python3
"""
Universal file compression worker.
Usage: compress_all_worker.py progress_file preset file1 file2 ...
preset: "Осторожно" | "Баланс" | "Агрессивно"
Output: <stem>_c.<ext> next to original (skipped if result is not smaller).
"""
import sys, json, subprocess, shutil, tempfile, os, time
from pathlib import Path

progress_file = sys.argv[1]
preset        = sys.argv[2]
result_mode   = sys.argv[3]  # "Создать копию" | "В отдельную папку" | "Заменить оригинал"
files         = [f for f in sys.argv[4:] if f]

replace_mode = result_mode == "Заменить оригинал"
subdir_mode  = result_mode == "В отдельную папку"
SUBDIR       = "Сжатые"

# ── Preset settings ───────────────────────────────────────────────────────────
P = {
    "Осторожно":  {"jpg": 88, "webp": 83, "pngq": "75-90", "png": 2, "crf": 24, "speed": "slow",  "audio": 192, "pdf": "/printer"},
    "Баланс":     {"jpg": 82, "webp": 75, "pngq": "60-80", "png": 4, "crf": 28, "speed": "medium","audio": 128, "pdf": "/ebook"},
    "Агрессивно": {"jpg": 70, "webp": 60, "pngq": "40-65", "png": 6, "crf": 32, "speed": "fast",  "audio":  96, "pdf": "/screen"},
}[preset]

HAS_PNGQUANT  = shutil.which("pngquant")
HAS_OXIPNG    = shutil.which("oxipng")
HAS_OPTIPNG   = shutil.which("optipng")
HAS_JPEGOPTIM = shutil.which("jpegoptim")
HAS_GIFSICLE  = shutil.which("gifsicle")
HAS_SCOUR     = shutil.which("scour")
HAS_GS        = shutil.which("gs")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
AUDIO_EXT = {".mp3", ".aac", ".m4a", ".ogg", ".opus", ".wma"}
LOSSLESS_AUDIO = {".flac", ".wav", ".aiff"}
PDF_EXT   = {".pdf"}


def write(pct, label, folder=""):
    sfx = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{sfx}")


def fmt_size(b):
    if b >= 1_048_576: return f"{b / 1_048_576:.1f} MB"
    if b >= 1024:      return f"{b / 1024:.0f} KB"
    return f"{b} B"


def unique_dst(p: Path, suffix="_c", out_dir: Path = None) -> Path:
    if out_dir:
        out_dir.mkdir(exist_ok=True)
        dst = out_dir / p.name
    else:
        dst = p.parent / f"{p.stem}{suffix}{p.suffix}"
    c, stem = 1, dst.stem
    while dst.exists():
        dst = dst.parent / f"{stem}_{c}{dst.suffix}"
        c += 1
    return dst


def probe_format(src) -> dict:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", src],
            capture_output=True,
        )
        return json.loads(r.stdout).get("format", {})
    except Exception:
        return {}

def probe_bitrate(src) -> int:
    return int(probe_format(src).get("bit_rate", 0)) // 1000

def probe_duration_us(src) -> int:
    try:
        return int(float(probe_format(src).get("duration", 0)) * 1_000_000)
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
        if HAS_PNGQUANT:
            r = subprocess.run(
                ["pngquant", f"--quality={P['pngq']}", "--strip",
                 "--output", str(dst), "--force", "--", str(src)],
                capture_output=True,
            )
            # returncode 98 = can't meet quality floor, dst not created → "already optimal"
            if r.returncode == 98:
                return subprocess.CompletedProcess(r.args, 0)
            return r
        elif HAS_OXIPNG:
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
        if HAS_JPEGOPTIM:
            with open(str(dst), "wb") as f:
                return subprocess.run(
                    ["jpegoptim", f"--max={P['jpg']}", "--strip-all", "--stdout", str(src)],
                    stdout=f, stderr=subprocess.DEVNULL,
                )
        else:
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

    elif ext == ".svg":
        if HAS_SCOUR:
            return subprocess.run(
                ["scour", "--enable-viewboxing", "--enable-id-stripping",
                 "--enable-comment-stripping", "--shorten-ids", "--remove-metadata",
                 "-i", str(src), "-o", str(dst)],
                capture_output=True,
            )
        else:
            return None  # no SVG tool


class _Result:
    def __init__(self, code): self.returncode = code


def _encoder_cmds(src: Path) -> list[list[str]]:
    """Return ffmpeg command prefixes to try, in priority order."""
    crf    = str(P["crf"])
    common = ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
    cmds   = []

    # VAAPI — Intel / AMD
    dri = list(Path("/dev/dri").glob("render*")) if Path("/dev/dri").exists() else []
    if dri:
        cmds.append(["ffmpeg", "-y", "-vaapi_device", str(dri[0]),
                     "-i", str(src), "-vf", "format=nv12,hwupload",
                     "-c:v", "h264_vaapi", "-qp", crf] + common)

    # NVENC — NVIDIA
    if shutil.which("nvidia-smi"):
        cmds.append(["ffmpeg", "-y", "-i", str(src),
                     "-c:v", "h264_nvenc", "-cq", crf, "-preset", "p4"] + common)

    # Software fallback
    cmds.append(["ffmpeg", "-y", "-i", str(src),
                 "-c:v", "libx264", "-crf", crf, "-preset", P["speed"]] + common)

    return cmds


def compress_video(src: Path, dst: Path, i: int, total: int) -> _Result:
    dur_us = probe_duration_us(str(src))

    for cmd in _encoder_cmds(src):
        prog_tmp = tempfile.mktemp(prefix="ffcomp_prog_")
        err_tmp  = tempfile.mktemp(prefix="ffcomp_err_")
        proc = subprocess.Popen(
            cmd + ["-progress", prog_tmp, str(dst)],
            stderr=open(err_tmp, "w"), stdout=subprocess.DEVNULL,
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
                                  f"({i+1}/{total}) {src.name}", str(src.parent))
                        break
            except Exception:
                pass
        for tmp in (prog_tmp, err_tmp):
            try: os.unlink(tmp)
            except FileNotFoundError: pass

        if proc.returncode == 0:
            return _Result(0)
        dst.unlink(missing_ok=True)  # clean up failed attempt before retry

    return _Result(1)


def compress_audio(src: Path, dst: Path) -> _Result | None:
    current_kbps = probe_bitrate(str(src))
    if current_kbps and current_kbps <= P["audio"]:
        return None  # already at or below target — skip

    ext = src.suffix.lower()
    codec_map = {".mp3": ("libmp3lame", []), ".aac": ("aac", []),
                 ".m4a": ("aac", []), ".ogg": ("libvorbis", []),
                 ".opus": ("libopus", []), ".wma": ("wmav2", [])}
    codec, extra = codec_map.get(ext, ("libopus", []))

    err_tmp = tempfile.mktemp(prefix="ffaud_err_")
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-i", str(src),
         "-c:a", codec, "-b:a", f"{P['audio']}k"] + extra + [str(dst)],
        stderr=open(err_tmp, "w"), stdout=subprocess.DEVNULL,
    )
    proc.wait()
    try: os.unlink(err_tmp)
    except FileNotFoundError: pass
    return _Result(proc.returncode)


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
total       = len(files)
results     = {"ok": 0, "skip": 0, "err": 0}
total_saved = 0
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

    out_dir = (src.parent / SUBDIR) if subdir_mode else None
    dst = unique_dst(src, out_dir=out_dir)

    # Choose compressor
    if ext in IMAGE_EXT:
        result = compress_image(src, dst)
    elif ext in VIDEO_EXT:
        result = compress_video(src, dst, i, total)
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

    saved_bytes  = src.stat().st_size - dst.stat().st_size
    total_saved += saved_bytes
    saved_pct    = saved_bytes * 100 // src.stat().st_size
    if replace_mode:
        shutil.copystat(src, dst)
        dst.replace(src)
    write((i+1)*100//total, f"✓ {src.name} (−{saved_pct}%)", str(src.parent))
    results["ok"] += 1

# ── Finish ────────────────────────────────────────────────────────────────────
saved_str = f" (−{fmt_size(total_saved)})" if total_saved > 0 else ""
parts = []
if results["ok"]:   parts.append(f"Сжато: {results['ok']}{saved_str}")
if results["skip"]: parts.append(f"Пропущено: {results['skip']}")
msg = ", ".join(parts) or "Нечего сжимать"

if results["err"]:
    subprocess.run(["notify-send", "Сжать", f"{msg}\nОшибок: {results['err']}", "-i", "dialog-warning"])
    write(100, f"Ошибок: {results['err']}")
else:
    src_dirs = list(dict.fromkeys(str(Path(f).parent) for f in files))
    if subdir_mode:
        all_dirs = [str(Path(d) / SUBDIR) for d in src_dirs if (Path(d) / SUBDIR).exists()]
        all_dirs = all_dirs or src_dirs
    else:
        all_dirs = src_dirs
    Path(progress_file).write_text(f"DONE|{msg}|{':'.join(all_dirs)}")

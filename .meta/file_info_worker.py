#!/usr/bin/env python3
"""
Gather file metadata and output JSON for info_dialog.py.
JSON: {"title": "...", "subtitle": "...", "sections": [{"title": "...", "rows": [{"label": "...", "value": "..."}]}]}
"""
import sys, json, subprocess, mimetypes
from pathlib import Path
from datetime import datetime

path = Path(sys.argv[1])
sections = []


def size_str(n):
    for unit, div in [("ГБ", 1 << 30), ("МБ", 1 << 20), ("КБ", 1 << 10)]:
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} Б"


def dur_str(sec):
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def frac(s):
    """Parse "num/den" fraction string to float."""
    try:
        n, d = s.split("/")
        return int(n) / int(d)
    except Exception:
        return None


MONTH_RU = ["января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"]

# ── General ──────────────────────────────────────────────────────────────────
stat = path.stat()
mime, _ = mimetypes.guess_type(str(path))
mtime = datetime.fromtimestamp(stat.st_mtime)
mtime_str = f"{mtime.day} {MONTH_RU[mtime.month - 1]} {mtime.year},  {mtime.strftime('%H:%M')}"

sections.append({"title": "Основное", "rows": [
    {"label": "Тип",      "value": mime or path.suffix.lstrip(".").upper() or "Неизвестно"},
    {"label": "Размер",   "value": size_str(stat.st_size)},
    {"label": "Изменён",  "value": mtime_str},
    {"label": "Папка",    "value": str(path.parent)},
]})

ext = path.suffix.lower().lstrip(".")

# ── Video / Audio via ffprobe ─────────────────────────────────────────────────
VIDEO_EXT = {"mp4", "mkv", "avi", "mov", "webm", "flv", "ts", "m2ts", "wmv"}
AUDIO_EXT = {"mp3", "flac", "wav", "ogg", "m4a", "aac", "opus", "wma"}

if ext in VIDEO_EXT | AUDIO_EXT:
    try:
        raw = subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            stderr=subprocess.DEVNULL,
        )
        data = json.loads(raw)
        fmt = data.get("format", {})
        dur = float(fmt.get("duration", 0))
        if dur:
            sections[0]["rows"].insert(0, {"label": "Длительность", "value": dur_str(dur)})
        br = int(fmt.get("bit_rate", 0))
        if br:
            sections[0]["rows"].append({"label": "Общий битрейт", "value": f"{br // 1000} кбит/с"})

        # Tags (title, artist, album…)
        tags = fmt.get("tags", {})
        tag_rows = []
        for key, ru in [("title", "Название"), ("artist", "Исполнитель"),
                        ("album", "Альбом"), ("date", "Год"), ("comment", "Комментарий")]:
            val = tags.get(key) or tags.get(key.upper())
            if val:
                tag_rows.append({"label": ru, "value": val})
        if tag_rows:
            sections.append({"title": "Метаданные", "rows": tag_rows})

        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                rows = [{"label": "Кодек", "value": s.get("codec_name", "?").upper()}]
                w, h = s.get("width"), s.get("height")
                if w and h:
                    rows.append({"label": "Разрешение", "value": f"{w} × {h}"})
                fps = frac(s.get("r_frame_rate", "0/1"))
                if fps:
                    rows.append({"label": "FPS", "value": f"{fps:.3f}".rstrip("0").rstrip(".")})
                vbr = int(s.get("bit_rate", 0))
                if vbr:
                    rows.append({"label": "Битрейт", "value": f"{vbr // 1000} кбит/с"})
                pix = s.get("pix_fmt", "")
                if pix:
                    rows.append({"label": "Цветовой формат", "value": pix})
                profile = s.get("profile", "")
                if profile and profile != "unknown":
                    rows.append({"label": "Профиль", "value": profile})
                sections.append({"title": "Видеодорожка", "rows": rows})

            elif s.get("codec_type") == "audio":
                rows = [{"label": "Кодек", "value": s.get("codec_name", "?").upper()}]
                sr = s.get("sample_rate", "")
                if sr:
                    rows.append({"label": "Частота", "value": f"{int(sr) // 1000} кГц"})
                ch = s.get("channels", "")
                chl = s.get("channel_layout", "")
                if ch:
                    rows.append({"label": "Каналы", "value": f"{ch}" + (f" ({chl})" if chl else "")})
                abr = int(s.get("bit_rate", 0))
                if abr:
                    rows.append({"label": "Битрейт", "value": f"{abr // 1000} кбит/с"})
                sections.append({"title": "Аудиодорожка", "rows": rows})
    except Exception:
        pass

# ── Image via magick identify ─────────────────────────────────────────────────
IMAGE_EXT = {"jpg", "jpeg", "png", "webp", "gif", "tiff", "tif", "avif", "heic", "bmp", "ico"}

if ext in IMAGE_EXT:
    try:
        raw = subprocess.check_output(
            ["magick", "identify", "-verbose", str(path)],
            stderr=subprocess.DEVNULL, text=True,
        )
        rows = []
        exif = {}
        in_props = False
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("Properties:"):
                in_props = True
                continue
            if in_props:
                if not line.startswith("    ") and not line.startswith("\t"):
                    in_props = False
                elif "exif:" in stripped:
                    k, _, v = stripped.partition(": ")
                    exif[k.strip()] = v.strip()
                continue
            if stripped.startswith("Geometry:"):
                geom = stripped.split(":", 1)[1].strip().split("+")[0]
                if "x" in geom:
                    w, h = geom.split("x")
                    rows.append({"label": "Разрешение", "value": f"{w} × {h}"})
            elif stripped.startswith("Colorspace:"):
                rows.append({"label": "Цветовое пространство", "value": stripped.split(":", 1)[1].strip()})
            elif stripped.startswith("Depth:"):
                rows.append({"label": "Глубина цвета", "value": stripped.split(":", 1)[1].strip()})
            elif stripped.startswith("Resolution:") and "PixelsPerInch" not in raw:
                rows.append({"label": "DPI", "value": stripped.split(":", 1)[1].strip()})

        if rows:
            sections.append({"title": "Изображение", "rows": rows})

        # EXIF
        exif_rows = []
        if exif.get("exif:Make"):
            model = exif.get("exif:Model", "")
            make  = exif.get("exif:Make", "")
            exif_rows.append({"label": "Камера", "value": f"{make} {model}".strip()})
        if exif.get("exif:DateTimeOriginal"):
            exif_rows.append({"label": "Дата съёмки", "value": exif["exif:DateTimeOriginal"].replace(":", ".", 2)})
        if exif.get("exif:ExposureTime"):
            exif_rows.append({"label": "Выдержка", "value": exif["exif:ExposureTime"] + " с"})
        if exif.get("exif:FNumber"):
            fn = frac(exif["exif:FNumber"])
            if fn:
                exif_rows.append({"label": "Диафрагма", "value": f"f/{fn:.1f}"})
        if exif.get("exif:ISOSpeedRatings"):
            exif_rows.append({"label": "ISO", "value": exif["exif:ISOSpeedRatings"]})
        if exif.get("exif:FocalLength") and "FocalLengthIn35" not in exif.get("exif:FocalLength", ""):
            fl = frac(exif["exif:FocalLength"])
            if fl:
                exif_rows.append({"label": "Фокусное расстояние", "value": f"{int(fl)} мм"})
        if exif.get("exif:GPSLatitude"):
            exif_rows.append({"label": "GPS", "value": f"{exif['exif:GPSLatitude']}, {exif.get('exif:GPSLongitude', '')}"})
        if exif_rows:
            sections.append({"title": "EXIF", "rows": exif_rows})
    except Exception:
        pass

# ── Archive ───────────────────────────────────────────────────────────────────
import zipfile, tarfile as _tarfile

if ext == "zip" or path.name.endswith(".zip"):
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            total = sum(i.file_size for i in infos)
            rows = [
                {"label": "Файлов в архиве",   "value": str(len(infos))},
                {"label": "Размер без сжатия",  "value": size_str(total)},
            ]
            if total > 0:
                ratio = (1 - stat.st_size / total) * 100
                rows.append({"label": "Степень сжатия", "value": f"{ratio:.0f}%"})
            sections.append({"title": "Архив", "rows": rows})
    except Exception:
        pass
elif any(path.name.endswith(s) for s in [".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".tar"]):
    try:
        with _tarfile.open(path) as t:
            members = [m for m in t.getmembers() if m.isfile()]
            total = sum(m.size for m in members)
            rows = [
                {"label": "Файлов в архиве",   "value": str(len(members))},
                {"label": "Размер без сжатия",  "value": size_str(total)},
            ]
            if total > 0:
                ratio = (1 - stat.st_size / total) * 100
                rows.append({"label": "Степень сжатия", "value": f"{ratio:.0f}%"})
            sections.append({"title": "Архив", "rows": rows})
    except Exception:
        pass

# ── Text / Code ───────────────────────────────────────────────────────────────
TEXT_EXT = {"txt", "md", "py", "js", "ts", "jsx", "tsx", "css", "html",
            "json", "yaml", "yml", "toml", "sh", "bash", "csv", "xml", "log", "ini", "cfg"}

if ext in TEXT_EXT:
    try:
        text = path.read_text(errors="replace")
        sections.append({"title": "Содержимое", "rows": [
            {"label": "Строк",    "value": str(len(text.splitlines()))},
            {"label": "Слов",     "value": str(len(text.split()))},
            {"label": "Символов", "value": str(len(text))},
        ]})
    except Exception:
        pass

print(json.dumps({"title": path.name, "sections": sections}, ensure_ascii=False))

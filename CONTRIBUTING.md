# Как добавить новый скрипт

## Структура `.meta/`

```
.meta/
├── indicator.py        # Трей-индикатор (GTK3 + AppIndicator3)
├── pick.py             # Диалог выбора (GTK4 + Libadwaita)
└── *_worker.py         # Фоновый воркер для каждого скрипта
```

---

## 1. Диалог выбора — `pick.py`

Вызывается из bash, возвращает выбранное значение в stdout.

```bash
SCRIPTS_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
PYTHON="/usr/bin/python3"

result=$("$PYTHON" "$SCRIPTS_ROOT/.meta/pick.py" \
    "Заголовок окна" \
    "Описание под заголовком" \
    "Вариант 1|подпись под вариантом" \
    "Вариант 2|подпись" \
    "Вариант 3|подпись") || exit 0
```

Если пользователь закрыл диалог — `pick.py` выходит с кодом 1, `|| exit 0` завершает скрипт.

---

## 2. Фоновый воркер + трей-индикатор

Паттерн для любой долгой операции:

**В bash-скрипте:**
```bash
PROGRESS_FILE=$(mktemp /tmp/my-script-XXXXX)

export GI_TYPELIB_PATH="/usr/lib64/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"

nohup "$PYTHON" "$SCRIPTS_ROOT/.meta/my_worker.py" \
    "$PROGRESS_FILE" [аргументы] \
    >/tmp/my-script-worker.log 2>&1 &

exec "$PYTHON" "$SCRIPTS_ROOT/.meta/indicator.py" "$PROGRESS_FILE"
```

`exec` заменяет bash-процесс индикатором — когда индикатор закрывается, скрипт завершается.

**В воркере (`my_worker.py`):**
```python
from pathlib import Path
import subprocess, sys

progress_file = sys.argv[1]

def write(pct, label, folder=""):
    suffix = f"|{folder}" if folder else ""
    Path(progress_file).write_text(f"{pct}|{label}{suffix}")

# Во время работы:
write(42, "(2/5) filename.mp4", "/home/user/Videos")

# Завершение — одна папка:
Path(progress_file).write_text("DONE|Готово: 5 файлов|/home/user/Videos")

# Завершение — несколько папок:
dirs = ":".join(["/папка1", "/папка2"])
Path(progress_file).write_text(f"DONE|Готово: 5 файлов|{dirs}")

# Ошибка:
subprocess.run(["notify-send", "Название", "Текст ошибки", "-i", "dialog-warning"])
write(100, "Ошибок: 2")
```

---

## 3. Протокол progress-файла

| Воркер пишет | Индикатор делает |
|---|---|
| `42\|label` | Показывает `⠋ 42%`, текст в меню |
| `42\|label\|/path` | То же + активирует "Открыть папку" |
| `DONE\|msg` | Иконка → ✓, закрывается через 3с |
| `DONE\|msg\|/p1:/p2` | То же + "Открыть папки (2)" через `nautilus /p1 /p2` |

---

## 4. Уведомления вместо диалогов

```bash
# Успех (из bash)
notify-send "Название" "Готово!" -i video-x-generic

# Ошибка (из bash)
notify-send "Название" "Что-то пошло не так" -i dialog-warning

# Из Python (воркер)
subprocess.run(["notify-send", "Название", "Текст", "-i", "dialog-warning"])
```

---

## 5. Шаблон нового скрипта

```bash
#!/usr/bin/env bash
set -eo pipefail

SCRIPTS_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
PYTHON="/usr/bin/python3"

mapfile -t files <<< "$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS"

if [ ${#files[@]} -eq 0 ] || [ -z "${files[0]}" ]; then
    notify-send "Название" "Файлы не выбраны." -i dialog-error
    exit 1
fi

# Диалог выбора (если нужен)
choice=$("$PYTHON" "$SCRIPTS_ROOT/.meta/pick.py" \
    "Заголовок" "Описание" \
    "Опция 1|пояснение" \
    "Опция 2|пояснение") || exit 0

# Воркер + индикатор
PROGRESS_FILE=$(mktemp /tmp/my-script-XXXXX)
export GI_TYPELIB_PATH="/usr/lib64/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"

nohup "$PYTHON" "$SCRIPTS_ROOT/.meta/my_worker.py" \
    "$PROGRESS_FILE" "$choice" "${files[@]}" \
    >/tmp/my-script-worker.log 2>&1 &

exec "$PYTHON" "$SCRIPTS_ROOT/.meta/indicator.py" "$PROGRESS_FILE"
```

---

## Зависимости системы

| Утилита | Для чего |
|---|---|
| `/usr/bin/python3` | Диалоги и индикатор (GTK3/GTK4 уже в системе Fedora) |
| `ffmpeg` / `ffprobe` | Видео-скрипты |
| `imagemagick` | Скрипты изображений |
| `notify-send` | Уведомления (пакет `libnotify`) |
| `nautilus` | Открытие папок из индикатора |

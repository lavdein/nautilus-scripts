# Как добавить новый скрипт

## Структура `.meta/`

```
.meta/
├── indicator.py        # Трей-индикатор (GTK3 + AppIndicator3)
├── pick.py             # Диалог выбора одного варианта (GTK4 + Libadwaita)
├── form.py             # Диалог с несколькими параметрами (GTK4 + Libadwaita)
└── *_worker.py         # Фоновый воркер для каждого скрипта
```

---

## Принципы диалогов

**Всё в одном окне.** Никаких последовательных диалогов — если пользователю нужно выбрать несколько параметров, они должны быть в одном окне через `form.py`.

**Размер окна подстраивается под контент.** Никаких фиксированных `default_height`. Ширина фиксируется на 440px, высота — автоматически.

---

## 1. Один параметр — `pick.py`

Список вариантов, пользователь выбирает один. Возвращает текст до `|` в stdout.

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

## 2. Несколько параметров — `form.py`

Несколько выпадающих списков в одном окне. Возвращает значения через `|` в stdout.

```bash
OPTIONS=$("$PYTHON" "$SCRIPTS_ROOT/.meta/form.py" \
    "Заголовок окна" \
    "Описание (количество файлов и т.п.)" \
    "Кнопка OK" \
    "Параметр 1:вариант1|вариант2|вариант3" \
    "Параметр 2:вариантA|вариантB") || exit 0

param1=$(echo "$OPTIONS" | cut -d'|' -f1)
param2=$(echo "$OPTIONS" | cut -d'|' -f2)
```

Используйте `form.py` всегда, когда нужно выбрать больше одного параметра.

---

## 3. Фоновый воркер + трей-индикатор

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

## 4. Протокол progress-файла

| Воркер пишет | Индикатор делает |
|---|---|
| `42\|label` | Показывает `⠋ 42%`, текст в меню |
| `42\|label\|/path` | То же + активирует "Открыть папку" |
| `DONE\|msg` | Иконка → ✓, закрывается через 3с |
| `DONE\|msg\|/p1:/p2` | То же + "Открыть папки (2)" через `nautilus /p1 /p2` |

---

## 5. Уведомления вместо диалогов

```bash
# Успех (из bash)
notify-send "Название" "Готово!" -i video-x-generic

# Ошибка (из bash)
notify-send "Название" "Что-то пошло не так" -i dialog-warning

# Из Python (воркер)
subprocess.run(["notify-send", "Название", "Текст", "-i", "dialog-warning"])
```

---

## 6. Шаблон нового скрипта

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

# Один параметр:
choice=$("$PYTHON" "$SCRIPTS_ROOT/.meta/pick.py" \
    "Заголовок" "Описание" \
    "Опция 1|пояснение" \
    "Опция 2|пояснение") || exit 0

# Несколько параметров — всё в одном окне:
OPTIONS=$("$PYTHON" "$SCRIPTS_ROOT/.meta/form.py" \
    "Заголовок" "${#files[@]} файл(ов)" "Начать" \
    "Параметр 1:опция1|опция2" \
    "Параметр 2:A|B|C") || exit 0
p1=$(echo "$OPTIONS" | cut -d'|' -f1)
p2=$(echo "$OPTIONS" | cut -d'|' -f2)

# Воркер + индикатор
PROGRESS_FILE=$(mktemp /tmp/my-script-XXXXX)
export GI_TYPELIB_PATH="/usr/lib64/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"

nohup "$PYTHON" "$SCRIPTS_ROOT/.meta/my_worker.py" \
    "$PROGRESS_FILE" "$p1" "$p2" "${files[@]}" \
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

#!/usr/bin/env python3
"""
Shared system-tray progress indicator for Nautilus scripts.
Uses pystray instead of AppIndicator3.

Progress file protocol:
  "pct|label|/folder"     — update spinner and label
  "DONE|msg|/f1:/f2:/f3"  — notify, show ✓, wait for user to close
  "DONE|msg"              — same but no folder to open
"""
import sys, os, subprocess, time, threading
from pathlib import Path
from PIL import Image
import pystray

progress_file = sys.argv[1]
notify_title  = sys.argv[2] if len(sys.argv) > 2 else "Готово"

SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

state = {"folders": [], "done": False, "info": "Подготовка..."}


def _open_folders(icon, item):
    if state["folders"]:
        subprocess.Popen(["nautilus"] + state["folders"])


def _quit(icon, item):
    icon.stop()


menu = pystray.Menu(
    pystray.MenuItem(lambda item: state["info"], None, enabled=False),
    pystray.MenuItem(
        lambda item: "Открыть папки" if len(state["folders"]) > 1 else "Открыть папку",
        _open_folders,
        enabled=lambda item: bool(state["folders"]),
    ),
    pystray.Menu.SEPARATOR,
    pystray.MenuItem(lambda item: "Закрыть" if state["done"] else "Отменить", _quit),
)

icon = pystray.Icon(
    "nautilus-progress",
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)),
    "Подготовка...",
    menu,
)


def poll():
    tick = 0
    while True:
        time.sleep(0.4)
        try:
            data = Path(progress_file).read_text().strip()
        except FileNotFoundError:
            icon.stop()
            return

        parts = data.split("|", 2)

        if parts[0] == "DONE":
            msg   = parts[1] if len(parts) > 1 else ""
            fstr  = parts[2] if len(parts) > 2 else ""
            state["folders"] = [p for p in fstr.split(":") if p]
            state["done"]    = True
            state["info"]    = msg
            icon.title = " ✓"
            subprocess.run(["notify-send", "--app-name", notify_title, notify_title, msg])
            return

        pct    = parts[0]
        label  = parts[1] if len(parts) > 1 else ""
        folder = parts[2] if len(parts) > 2 else ""
        if folder:
            state["folders"] = [folder]
        state["info"] = label
        icon.title = f"{SPINNER[tick % len(SPINNER)]} {pct}%"
        tick += 1


threading.Thread(target=poll, daemon=True).start()
icon.run()

try:
    os.unlink(progress_file)
except OSError:
    pass

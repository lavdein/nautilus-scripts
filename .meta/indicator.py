#!/usr/bin/env python3
"""
Shared system-tray progress indicator for Nautilus scripts.
Usage: indicator.py progress_file

Progress file protocol:
  "pct|label|/folder"     — update percentage, label, current folder
  "DONE|msg|/f1:/f2:/f3"  — show ✓, enable folder open, quit after 3s
  "DONE|msg"              — same but no folder to open
"""
import gi, sys, os, subprocess
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Gtk', '3.0')
from gi.repository import AppIndicator3, Gtk, GLib

progress_file = sys.argv[1]

SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
tick = [0]

# Mutable folder state — updated by poll(), read by open handler
folder_state = {"paths": []}

indicator = AppIndicator3.Indicator.new(
    "nautilus-script-progress",
    "emblem-synchronizing",
    AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
)
indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
indicator.set_label(f"{SPINNER[0]}  0%", "⠏ 100%")

menu      = Gtk.Menu()
item_info = Gtk.MenuItem(label="Подготовка...")
item_open = Gtk.MenuItem(label="Открыть папку")
item_open.set_sensitive(False)
item_sep  = Gtk.SeparatorMenuItem()
item_quit = Gtk.MenuItem(label="Отменить")

item_quit.connect("activate", lambda _: Gtk.main_quit())
item_open.connect("activate", lambda _: (
    subprocess.Popen(["nautilus"] + folder_state["paths"])
    if folder_state["paths"] else None
))

for w in (item_info, item_open, item_sep, item_quit):
    menu.append(w)
menu.show_all()
indicator.set_menu(menu)


def poll():
    try:
        data = open(progress_file).read().strip()
    except FileNotFoundError:
        Gtk.main_quit()
        return False

    parts = data.split("|", 2)

    if parts[0] == "DONE":
        msg    = parts[1] if len(parts) > 1 else ""
        fstr   = parts[2] if len(parts) > 2 else ""
        paths  = [p for p in fstr.split(":") if p]
        if paths:
            folder_state["paths"] = paths
            n = len(paths)
            item_open.set_label("Открыть папку" if n == 1 else f"Открыть папки ({n})")
            item_open.set_sensitive(True)
        indicator.set_icon("emblem-default")
        indicator.set_label(" ✓", " ✓")
        item_info.set_label(msg)
        GLib.timeout_add(3000, Gtk.main_quit)
        return False

    pct    = parts[0]
    label  = parts[1] if len(parts) > 1 else ""
    folder = parts[2] if len(parts) > 2 else ""

    if folder:
        folder_state["paths"] = [folder]
        item_open.set_sensitive(True)

    spin = SPINNER[tick[0] % len(SPINNER)]
    tick[0] += 1
    indicator.set_label(f"{spin} {pct}%", "⠏ 100%")
    item_info.set_label(label)
    return True


GLib.timeout_add(400, poll)
Gtk.main()

try:
    os.unlink(progress_file)
except OSError:
    pass

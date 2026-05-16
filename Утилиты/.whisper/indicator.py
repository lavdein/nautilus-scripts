#!/usr/bin/env python3
import gi, sys, os
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Gtk', '3.0')
from gi.repository import AppIndicator3, Gtk, GLib

progress_file = sys.argv[1]

SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
tick = [0]

indicator = AppIndicator3.Indicator.new(
    "nautilus-script-progress",
    "emblem-synchronizing",
    AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
)
indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
indicator.set_label(f"{SPINNER[0]}  0%", "⠏ 100%")

menu = Gtk.Menu()
item_info = Gtk.MenuItem(label="Подготовка...")
item_sep  = Gtk.SeparatorMenuItem()
item_quit = Gtk.MenuItem(label="Отменить")
item_quit.connect("activate", lambda _: Gtk.main_quit())
for w in (item_info, item_sep, item_quit):
    menu.append(w)
menu.show_all()
indicator.set_menu(menu)


def poll():
    try:
        data = open(progress_file).read().strip()
    except FileNotFoundError:
        Gtk.main_quit()
        return False

    if data.startswith("DONE|"):
        indicator.set_icon("emblem-default")
        indicator.set_label(" ✓", " ✓")
        item_info.set_label(data[5:])
        GLib.timeout_add(3000, Gtk.main_quit)
        return False

    pct, _, name = data.partition("|")
    spin = SPINNER[tick[0] % len(SPINNER)]
    tick[0] += 1
    indicator.set_label(f"{spin} {pct}%", "⠏ 100%")
    item_info.set_label(name)
    return True


GLib.timeout_add(400, poll)
Gtk.main()

try:
    os.unlink(progress_file)
except OSError:
    pass

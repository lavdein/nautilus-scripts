#!/usr/bin/env python3
"""
Generic Adwaita pick dialog for Nautilus scripts.

Usage:
    pick.py "Window title" "Description" "LABEL|subtitle" "LABEL2|subtitle2" ...

Prints chosen label (part before |) to stdout.
Exit 0 = picked, exit 1 = cancelled.
"""

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

title = sys.argv[1]
description = sys.argv[2] if len(sys.argv) > 2 else ""
options = sys.argv[3:]

selected = []


class PickApp(Adw.Application):
    def do_activate(self):
        win = Adw.ApplicationWindow(
            application=self,
            default_width=440,
            resizable=False,
        )
        win.set_title(title)

        toolbar_view = Adw.ToolbarView()
        win.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)
        cancel_btn = Gtk.Button(label="Отмена")
        cancel_btn.connect("clicked", lambda *_: self.quit())
        header.pack_start(cancel_btn)
        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        scroll.set_propagate_natural_height(True)
        toolbar_view.set_content(scroll)

        clamp = Adw.Clamp(maximum_size=460, tightening_threshold=420)
        scroll.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(18)
        box.set_margin_bottom(24)
        box.set_margin_start(18)
        box.set_margin_end(18)
        clamp.set_child(box)

        # Title + description
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(header_box)

        title_lbl = Gtk.Label(label=title)
        title_lbl.add_css_class("title-2")
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_wrap(True)
        header_box.append(title_lbl)

        if description:
            desc_lbl = Gtk.Label(label=description)
            desc_lbl.add_css_class("dim-label")
            desc_lbl.set_halign(Gtk.Align.START)
            desc_lbl.set_wrap(True)
            header_box.append(desc_lbl)

        group = Adw.PreferencesGroup()
        box.append(group)

        for opt in options:
            if opt.startswith("---"):
                group = Adw.PreferencesGroup()
                group.set_title(opt[3:])
                box.append(group)
                continue

            parts = opt.split("|", 1)
            label_text = parts[0]
            subtitle_text = parts[1] if len(parts) > 1 else ""

            row = Adw.ActionRow(title=label_text, activatable=True)
            if subtitle_text:
                row.set_subtitle(subtitle_text)
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.connect("activated", self._on_pick, label_text)
            group.add(row)

        win.present()

    def _on_pick(self, _row, value):
        selected.append(value)
        self.quit()


app = PickApp(application_id="io.github.lavdein.nautilus.pick")
app.run(None)

if not selected:
    sys.exit(1)

print(selected[0])

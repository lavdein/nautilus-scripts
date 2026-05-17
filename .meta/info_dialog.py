#!/usr/bin/env python3
"""
Adwaita info dialog with sections and rows.
Reads JSON from stdin: {"title": "...", "sections": [{"title": "...", "rows": [{"label": "...", "value": "..."}]}]}
"""
import sys, json
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

data     = json.loads(sys.stdin.read())
title    = data.get("title", "Информация")
sections = data.get("sections", [])


class InfoApp(Adw.Application):
    def do_activate(self):
        win = Adw.ApplicationWindow(
            application=self,
            default_width=480,
            resizable=True,
        )
        win.set_title(title)

        toolbar_view = Adw.ToolbarView()
        win.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_show_start_title_buttons(False)

        win_title = Adw.WindowTitle()
        win_title.set_title(title)
        header.set_title_widget(win_title)
        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        scroll.set_propagate_natural_height(True)
        scroll.set_max_content_height(700)
        toolbar_view.set_content(scroll)

        clamp = Adw.Clamp(maximum_size=500, tightening_threshold=460)
        scroll.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(18)
        box.set_margin_bottom(24)
        box.set_margin_start(18)
        box.set_margin_end(18)
        clamp.set_child(box)

        for section in sections:
            group = Adw.PreferencesGroup()
            group.set_title(section.get("title", ""))
            box.append(group)

            for item in section.get("rows", []):
                label = item.get("label", "")
                value = item.get("value", "")

                # value is the primary text, label is the subtitle (Adwaita convention for properties)
                row = Adw.ActionRow()
                row.set_title(value)
                row.set_subtitle(label)
                row.set_activatable(False)
                group.add(row)

        win.present()


InfoApp(application_id="io.github.lavdein.nautilus.fileinfo").run(None)

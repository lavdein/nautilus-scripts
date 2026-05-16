#!/usr/bin/env python3
"""
Multi-parameter Adwaita form dialog using ComboRow.
Usage: form.py "Title" "Description" "OK button label" "Label1:opt1|opt2" "Label2:optA|optB" ...
Prints selected values pipe-separated to stdout.
Exit 0 = confirmed, exit 1 = cancelled.
"""
import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

title      = sys.argv[1]
description = sys.argv[2]
ok_label   = sys.argv[3]
fields     = sys.argv[4:]   # each: "Label:opt1|opt2|opt3"

confirmed  = []
combo_data = []   # list of (ComboRow, StringList)


class FormApp(Adw.Application):
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
        cancel_btn = Gtk.Button(label="Отмена")
        cancel_btn.connect("clicked", lambda *_: self.quit())
        header.pack_start(cancel_btn)

        ok_btn = Gtk.Button(label=ok_label)
        ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", self._on_confirm)
        header.pack_end(ok_btn)

        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        toolbar_view.set_content(scroll)

        clamp = Adw.Clamp(maximum_size=460, tightening_threshold=420)
        scroll.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(18)
        box.set_margin_bottom(24)
        box.set_margin_start(18)
        box.set_margin_end(18)
        clamp.set_child(box)

        if description:
            desc_lbl = Gtk.Label(label=description)
            desc_lbl.add_css_class("dim-label")
            desc_lbl.set_halign(Gtk.Align.START)
            desc_lbl.set_wrap(True)
            box.append(desc_lbl)

        group = Adw.PreferencesGroup()
        box.append(group)

        for field in fields:
            label, _, opts_str = field.partition(":")
            opts = opts_str.split("|")

            string_list = Gtk.StringList.new(opts)
            row = Adw.ComboRow(title=label)
            row.set_model(string_list)
            group.add(row)
            combo_data.append((row, string_list))

        win.present()

    def _on_confirm(self, _):
        for row, model in combo_data:
            confirmed.append(model.get_string(row.get_selected()))
        self.quit()


FormApp(application_id="io.github.lavdein.nautilus.form").run(None)

if not confirmed:
    sys.exit(1)

print("|".join(confirmed))

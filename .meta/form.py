#!/usr/bin/env python3
"""
Multi-parameter Adwaita form dialog.

Field formats:
  "Label:opt1|opt2|opt3"             — ComboRow (dropdown)
  "Label:scale:min:max:default"      — Scale (slider), outputs integer
  "@N=Value|Label:..."               — any field type shown only when field N equals Value

Usage: form.py "Title" "Description" "OK label" field1 field2 ...
Prints all selected values pipe-separated to stdout (including hidden fields).
Exit 0 = confirmed, exit 1 = cancelled.
"""
import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

title       = sys.argv[1]
description = sys.argv[2]
ok_label    = sys.argv[3]
fields      = sys.argv[4:]

confirmed    = []
field_data   = []   # list of (widget, get_value_fn)


def parse_fields(fields):
    result = []
    for field in fields:
        condition = None
        if field.startswith("@"):
            cond_end = field.index("|")
            cond_part = field[1:cond_end]
            field = field[cond_end + 1:]
            idx_str, _, cond_val = cond_part.partition("=")
            condition = (int(idx_str), cond_val)
        label, _, rest = field.partition(":")
        result.append((label, rest, condition))
    return result


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
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)
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

        if description:
            desc_lbl = Gtk.Label(label=description)
            desc_lbl.add_css_class("dim-label")
            desc_lbl.set_halign(Gtk.Align.START)
            desc_lbl.set_wrap(True)
            box.append(desc_lbl)

        group = Adw.PreferencesGroup()
        box.append(group)

        for label, rest, condition in parse_fields(fields):
            parts = rest.split(":")
            if parts[0] == "scale":
                _, min_v, max_v, default_v = parts
                widget, getter = self._make_scale_row(
                    label, float(min_v), float(max_v), float(default_v)
                )
            else:
                opts = rest.split("|")
                string_list = Gtk.StringList.new(opts)
                widget = Adw.ComboRow(title=label)
                widget.set_model(string_list)
                getter = lambda w=widget, m=string_list: m.get_string(w.get_selected())

            group.add(widget)
            field_data.append((widget, getter))

            if condition is not None:
                dep_idx, dep_val = condition
                dep_widget, dep_getter = field_data[dep_idx]

                def update_vis(_, __, w=widget, dg=dep_getter, dv=dep_val):
                    w.set_visible(dg() == dv)

                dep_widget.connect("notify::selected", update_vis)
                update_vis(None, None)

        win.present()

    def _make_scale_row(self, label, min_val, max_val, default_val):
        row = Adw.PreferencesRow()

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(12)
        outer.set_margin_end(12)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        lbl = Gtk.Label(label=label)
        lbl.set_hexpand(True)
        lbl.set_halign(Gtk.Align.START)

        val_lbl = Gtk.Label(label=str(int(default_val)))
        val_lbl.add_css_class("dim-label")
        val_lbl.set_width_chars(3)
        val_lbl.set_xalign(1)

        header.append(lbl)
        header.append(val_lbl)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min_val, max_val, 1)
        scale.set_value(default_val)
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.connect("value-changed",
                      lambda s, vl=val_lbl: vl.set_label(str(int(s.get_value()))))

        outer.append(header)
        outer.append(scale)
        row.set_child(outer)

        return row, lambda s=scale: str(int(s.get_value()))

    def _on_confirm(self, _):
        for _, getter in field_data:
            confirmed.append(getter())
        self.quit()


FormApp(application_id="io.github.lavdein.nautilus.form").run(None)

if not confirmed:
    sys.exit(1)

print("|".join(confirmed))

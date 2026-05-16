#!/usr/bin/env python3
"""
Display a read-only info dialog.
Usage: echo "text" | show_info.py "Window Title"
"""
import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

title = sys.argv[1] if len(sys.argv) > 1 else "Информация"
text  = sys.stdin.read().strip()


class InfoApp(Adw.Application):
    def do_activate(self):
        win = Adw.ApplicationWindow(
            application=self,
            default_width=420,
            default_height=460,
            resizable=True,
        )
        win.set_title(title)

        toolbar_view = Adw.ToolbarView()
        win.set_content(toolbar_view)
        toolbar_view.add_top_bar(Adw.HeaderBar())

        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        toolbar_view.set_content(scroll)

        clamp = Adw.Clamp(maximum_size=460, tightening_threshold=420)
        scroll.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)
        clamp.set_child(box)

        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.START)
        label.set_wrap(True)
        label.set_selectable(True)
        label.add_css_class("monospace")
        box.append(label)

        win.present()


InfoApp(application_id="io.github.lavdein.nautilus.info").run(None)

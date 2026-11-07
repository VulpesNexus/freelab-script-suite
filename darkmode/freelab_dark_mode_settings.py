#FLM: Dark Mode Settings
# -*- coding: utf-8 -*-
"""FreeLab dark mode settings, from FontLab's Scripts menu.

Theme: dark, or automatic (dark while Windows apps are dark, FontLab's own light
look while they are light, switching as Windows does). Mixed keeps FontLab's
light glyph canvases, font cells, and previews in a dark interface. Shade: how
dark the grays are. Every change shows at once; Cancel puts back what was there.
Switching dark mode off is Scripts > FreeLab > Toggle Dark Mode.

Valid Python 2.7 (FontLab 7) and Python 3.
"""

from __future__ import absolute_import, division, print_function

import os
import sys

DARK_MODE_MODULE = "freelab_dark_mode"
DARK_MODE_FILE = "freelab_dark_mode.py"
THEMES = (("dark", "Dark"), ("automatic", "Automatic (matches system theme)"))
MIXED = "Mixed (dark interface, light canvases)"
SHADES = (("dark", "Dark grays"), ("medium", "Medium grays"))
SYSTEM_CHECK_MS = 2000  # how often the open dialog looks at Windows' theme


def dark_mode_module():
    """The running dark mode, or the one next to this file, loaded without switching anything."""
    held = getattr(sys, "_freelab_dark_mode", None)  # dark mode's state keeps the running version
    module = (held.get("module") if isinstance(held, dict) else None) or sys.modules.get(DARK_MODE_MODULE)
    if module is not None and hasattr(module, "load_settings"):  # not a stub a failed load left
        return module
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, DARK_MODE_FILE)
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(DARK_MODE_MODULE)
            module.__file__ = path
            sys.modules[DARK_MODE_MODULE] = module
            with open(path, "rb") as handle:
                source = handle.read()
            exec(compile(source, DARK_MODE_FILE, "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(DARK_MODE_MODULE, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[DARK_MODE_MODULE] = module
            spec.loader.exec_module(module)
    finally:
        del os.environ["FREELAB_NO_AUTOSTART"]
    return module


def current_choice(settings, dm):
    """What the dialog shows: (theme, mixed, shade)."""
    theme = "automatic" if settings.get("follow_windows") else "dark"
    return theme, not dm.content_setting(settings), settings.get("shade", "dark")


def show_dialog():
    from PythonQt.QtGui import QDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QCheckBox, QPushButton, QLabel
    from PythonQt.QtGui import QButtonGroup
    from PythonQt.QtCore import Qt
    dm = dark_mode_module()
    settings = dm.load_settings()
    before = dict(dark=bool(settings.get("enabled")), content=dm.content_setting(settings),
                  follow_windows=bool(settings.get("follow_windows")), shade=settings.get("shade", "dark"))
    theme, mixed, shade = current_choice(settings, dm)
    dialog = QDialog()
    dialog.setWindowTitle("FreeLab Dark Mode")
    # No "?" in the title bar: it offered help this dialog does not have.
    flags = int(dialog.windowFlags()) if callable(dialog.windowFlags) else int(dialog.windowFlags)
    dialog.setWindowFlags(Qt.WindowFlags(flags & ~int(Qt.WindowContextHelpButtonHint)))
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Theme:"))
    themes, shades = {}, {}
    theme_group, shade_group = QButtonGroup(dialog), QButtonGroup(dialog)  # each its own exclusive group
    for key, label in THEMES:
        button = QRadioButton(label)
        button.setChecked(key == theme)
        layout.addWidget(button)
        theme_group.addButton(button)
        themes[key] = button
    mixed_box = QCheckBox(MIXED)
    mixed_box.setChecked(mixed)
    layout.addWidget(mixed_box)
    layout.addWidget(QLabel("Shade:"))
    for key, label in SHADES:
        button = QRadioButton(label)
        button.setChecked(key == shade)
        layout.addWidget(button)
        shade_group.addButton(button)
        shades[key] = button
    row = QHBoxLayout()
    row.addStretch(1)
    ok, cancel = QPushButton("OK"), QPushButton("Cancel")
    ok.setDefault(True)
    row.addWidget(ok)
    row.addWidget(cancel)
    layout.addLayout(row)
    ok.connect("clicked()", dialog.accept)
    cancel.connect("clicked()", dialog.reject)

    def chosen():
        follow = themes["automatic"].isChecked()
        picked = [key for key, button in shades.items() if button.isChecked()]
        return dict(dark=True, content=not mixed_box.isChecked(), follow_windows=follow,
                    shade=picked[0] if picked else "dark")

    shown = {"value": None}

    def preview(*_args):
        """Each change shows at once (applied as OK would; Cancel puts back what was there)."""
        choice = chosen()
        if choice != shown["value"]:
            shown["value"] = choice
            dm.configure(**choice)

    def system_light(*_args):
        """Under Automatic while Windows is light, FontLab is light: mixed and the shade do nothing until
        Windows turns dark, so they are grayed out; checked again every few seconds while the dialog is
        open, so a theme that changes on a schedule shows here too."""
        idle = themes["automatic"].isChecked() and not dm.windows_is_dark()
        mixed_box.setEnabled(not idle)
        for button in shades.values():
            button.setEnabled(not idle)

    for button in list(themes.values()) + list(shades.values()):
        button.connect("toggled(bool)", preview)
    mixed_box.connect("toggled(bool)", preview)
    themes["automatic"].connect("toggled(bool)", system_light)
    from PythonQt.QtCore import QTimer
    watch = QTimer(dialog)
    watch.setInterval(SYSTEM_CHECK_MS)
    watch.connect("timeout()", system_light)
    watch.start()
    system_light()
    if not dialog.exec_():
        if shown["value"] is not None:
            dm.configure(**before)
        return None
    result = dm.configure(**chosen())
    print("FreeLab dark mode: %s%s, %s." % (
        "automatic" if result.get("follow_windows") else "dark",
        ", mixed" if not dm.content_setting(result) else "",
        dict(SHADES).get(result.get("shade", "dark"), "Dark grays").lower()))
    return result


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_dark_mode_settings":
    show_dialog()

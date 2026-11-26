#FLM: Dark Mode Settings
# -*- coding: utf-8 -*-
"""FreeLab dark mode settings, from FontLab's Scripts menu.

Theme: dark, or automatic (dark while Windows apps are dark, FontLab's own light
look while they are light, switching as Windows does). Mixed keeps FontLab's
light glyph canvases, font cells, and previews in a dark interface. Shade: how
dark the grays are. Every change shows at once; Cancel puts back what was there.
Switching dark mode off is Scripts > FreeLab > Dark Mode.

Valid Python 2.7 (FontLab 7) and Python 3.
"""

from __future__ import absolute_import, division, print_function

import os
import sys

DARK_MODE_MODULE = "freelab_dark_mode"
DARK_MODE_FILE = "freelab_dark_mode.py"
THEMES = (("dark", "Dark"), ("automatic", "Automatic (follows Windows)"))
MIXED = "Mixed (dark interface, light canvases)"
SHADES = (("dark", "Dark grays"), ("medium", "Medium grays"))
# One tooltip per option, as Tab Docking Settings has (system_light grays the last two: said so)
AUTOMATIC_TIP = (u"Dark while Windows apps are set to dark, FontLab's own light look while they are light, "
                 u"switching as Windows does.")
IDLE_NOTE = u" Grayed under <i>Automatic</i> while Windows is light."
MIXED_TIP = u"Keeps FontLab's light glyph canvases, font cells, and previews in the dark interface." + IDLE_NOTE
SHADE_TIP = u"How dark the interface's grays are: dark grays, or medium grays with a lighter palette." + IDLE_NOTE
ENGINES = (("native", "Native (FontLab's colors changed as it paints)"),
           ("script", "Pixels (what FontLab drew, changed after)"))
ENGINE_NOTE = "The engine changes when you click OK; it takes a few seconds."
SYSTEM_CHECK_MS = 2000  # how often the open dialog looks at Windows' theme
SCRIPT_WINDOW_PROP = "mcpScriptWindow"  # FreeLab MCP's convention: the dialog is a script's, not FontLab's question


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


def main_window():
    """FontLab's main window, or None."""
    try:
        from PythonQt.QtGui import QApplication
        for widget in QApplication.topLevelWidgets():
            if widget.objectName == "MainWindow":
                return widget
    except Exception:
        pass
    return None


def held_dialogs():
    """Dialogs this script let go of and Qt has not deleted yet (or, with no FontLab main window to give
    them to, kept for the session): held in sys, never let go while PythonQt could delete them."""
    held = getattr(sys, "_freelab_dark_mode_settings_held", None)
    if held is None:
        held = sys._freelab_dark_mode_settings_held = []
    return held


def let_go(dialog, watch, slot, parented):
    """A closed settings dialog: its watch timer stopped and disconnected, then the dialog deleted once by
    Qt (deleteLater from a plain timer's slot, never from inside its own signals) when it has FontLab's
    main window as its parent, which PythonQt leaves to Qt. A parentless one (no main window found) is
    kept, hidden: PythonQt deletes a widget made from Python the moment its last reference goes."""
    from PythonQt.QtCore import QTimer
    try:
        watch.stop()
    except Exception:
        pass
    if slot is not None:
        try:
            watch.disconnect("timeout()", slot)
        except Exception:
            pass
    held = held_dialogs()
    held.append(dialog)
    if not parented:
        return

    def delete():
        try:
            dialog.deleteLater()
        except Exception:
            pass
        held[:] = [entry for entry in held if entry is not dialog]  # (only now let go)
    QTimer.singleShot(0, delete)


def show_dialog():
    """The settings dialog, modal; the settings chosen (None on Cancel). The dialog has FontLab's main
    window as its parent and is deleted once closed (let_go), its watch timer stopped first."""
    from PythonQt.QtGui import QDialog
    from PythonQt.QtCore import QTimer
    dm = dark_mode_module()
    main = main_window()
    dialog = QDialog(main) if main is not None else QDialog()  # (a parent: PythonQt leaves it to Qt)
    watch = QTimer(dialog)
    slots = {}
    try:
        return _run(dialog, watch, slots, dm)
    finally:
        let_go(dialog, watch, slots.get("watch"), main is not None)


def _run(dialog, watch, slots, dm):
    from PythonQt.QtGui import QVBoxLayout, QHBoxLayout, QRadioButton, QCheckBox, QPushButton, QLabel
    from PythonQt.QtGui import QButtonGroup
    from PythonQt.QtCore import Qt
    settings = dm.load_settings()
    before = dict(dark=bool(settings.get("enabled")), content=dm.content_setting(settings),
                  follow_windows=bool(settings.get("follow_windows")), shade=settings.get("shade", "dark"))
    has_engines = hasattr(dm, "engine_setting")  # a dark mode from before the native engine has one
    engine = dm.engine_setting(settings) if has_engines else "script"
    theme, mixed, shade = current_choice(settings, dm)
    dialog.setWindowTitle("FreeLab Dark Mode")
    # FreeLab's own dialog, not a question of FontLab's, for FreeLab MCP's window tools (its mcpScriptWindow
    # convention: a Qt property nothing else reads)
    dialog.setProperty(SCRIPT_WINDOW_PROP, True)
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
        if key == "automatic":
            button.setToolTip(AUTOMATIC_TIP)
        layout.addWidget(button)
        theme_group.addButton(button)
        themes[key] = button
    mixed_box = QCheckBox(MIXED)
    mixed_box.setToolTip(MIXED_TIP)
    mixed_box.setChecked(mixed)
    layout.addWidget(mixed_box)
    layout.addWidget(QLabel("Shade:"))
    for key, label in SHADES:
        button = QRadioButton(label)
        button.setToolTip(SHADE_TIP)
        button.setChecked(key == shade)
        layout.addWidget(button)
        shade_group.addButton(button)
        shades[key] = button
    engines = {}
    if has_engines:
        layout.addWidget(QLabel("Engine:"))
        engine_group = QButtonGroup(dialog)
        native_ready = os.path.isfile(dm.hooks_path())
        for key, label in ENGINES:
            if key == "native" and not native_ready:
                label += " (not installed: run tools\\install-fontlab.ps1)"
            button = QRadioButton(label)
            button.setChecked(key == engine)
            button.setEnabled(key != "native" or native_ready)
            layout.addWidget(button)
            engine_group.addButton(button)
            engines[key] = button
        layout.addWidget(QLabel(ENGINE_NOTE))
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
        """Each change shows at once (applied as OK would; Cancel puts back what was there). A Qt slot:
        nothing may escape it."""
        try:
            choice = chosen()
            if choice != shown["value"]:
                shown["value"] = choice
                dm.configure(**choice)
        except Exception as exc:
            print("FreeLab dark mode: the change could not be shown (%r)." % (exc,))  # repr: ASCII in Python 2

    def system_light(*_args):
        """Under Automatic while Windows is light, FontLab is light: mixed and the shade do nothing until
        Windows turns dark, so they are grayed out; checked again every few seconds while the dialog is
        open, so a theme that changes on a schedule shows here too. A Qt slot and a timer's: nothing
        may escape it."""
        try:
            idle = themes["automatic"].isChecked() and not dm.windows_is_dark()
            mixed_box.setEnabled(not idle)
            for button in shades.values():
                button.setEnabled(not idle)
            for key, button in engines.items():
                button.setEnabled(not idle and (key != "native" or os.path.isfile(dm.hooks_path())))
        except Exception:
            pass  # the controls stay as they were; the next check tries again

    for button in list(themes.values()) + list(shades.values()):
        button.connect("toggled(bool)", preview)
    mixed_box.connect("toggled(bool)", preview)
    themes["automatic"].connect("toggled(bool)", system_light)
    watch.setInterval(SYSTEM_CHECK_MS)
    slots["watch"] = system_light
    watch.connect("timeout()", system_light)
    watch.start()
    system_light()
    if not dialog.exec_():
        if shown["value"] is not None:
            dm.configure(**before)
        return None
    final = chosen()
    picked = [key for key, button in engines.items() if button.isChecked()]
    if picked:
        final["engine"] = picked[0]  # applied on OK only: switching engines takes several seconds
    result = dm.configure(**final)
    print("FreeLab dark mode: %s%s, %s%s." % (
        "automatic" if result.get("follow_windows") else "dark",
        ", mixed" if not dm.content_setting(result) else "",
        dict(SHADES).get(result.get("shade", "dark"), "Dark grays").lower(),
        ", native engine" if has_engines and dm.engine_setting(result) == "native" else ""))
    return result


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_dark_mode_settings":
    show_dialog()

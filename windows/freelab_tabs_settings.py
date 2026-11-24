#FLM: Tab Docking Settings
# -*- coding: utf-8 -*-
"""FreeLab tab docking settings, from FontLab's Scripts menu.

Two options: tabs released on or near the main tab bar dock there (and reorder that way), and tabs
never undock. OK applies them at once and switches tab docking on with them (off when both are
unticked); Cancel changes nothing. Switching tab docking off and on with the options last chosen is
Scripts > FreeLab > Tab Docking.

Valid Python 2.7 (FontLab 7) and Python 3.
"""

from __future__ import absolute_import, division, print_function

import os
import sys

TABS_MODULE = "freelab_tabs"
TABS_FILE = "freelab_tabs.py"
REORDER = u"Dock tabs released on or near the tab bar."
REORDER_TIP = (u"Drag a tab along the tab bar to reorder it: a tab released on or near the bar, or a window of "
               u"its own dragged there by its title bar, goes into the main window at that place. A window of its "
               u"own gets a <i>Dock</i> button, and a double-click on its tab docks it.")
NO_UNDOCK = u"Tabs cannot be undocked."
NO_UNDOCK_TIP = (u"A tab of the main window cannot be dragged out of it, and FontLab's <i>Undock</i> commands "
                 u"(<i>Window &gt; Docking</i>) are hidden. With <i>Dock tabs released on or near the tab bar</i> "
                 u"ticked too, a tab still moves along the tab bar; with it unticked, dragging a tab does nothing.")
OFF_NOTE = u"Tab docking is off: <i>OK</i> switches it on with these options (with both unticked, it stays off)."
SCRIPT_WINDOW_PROP = "mcpScriptWindow"  # FreeLab MCP's convention: the dialog is a script's, not FontLab's question


def tabs_module():
    """The running tab docking, or the one next to this file, loaded without starting anything."""
    held = getattr(sys, "_freelab_tabs_state", None)  # tab docking's state keeps the running version
    module = (held.get("module") if isinstance(held, dict) else None) or sys.modules.get(TABS_MODULE)
    if module is not None and hasattr(module, "configure"):  # (not an earlier version, nor a stub a failed load left)
        return module
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, TABS_FILE)
    before = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"  # loaded only: running it as a script would switch tab docking
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(TABS_MODULE)
            module.__file__ = path
            sys.modules[TABS_MODULE] = module
            with open(path, "rb") as handle:
                source = handle.read()
            exec(compile(source, TABS_FILE, "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(TABS_MODULE, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[TABS_MODULE] = module
            spec.loader.exec_module(module)
    finally:
        if before is None:
            del os.environ["FREELAB_NO_AUTOSTART"]
        else:
            os.environ["FREELAB_NO_AUTOSTART"] = before
    return module


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
    held = getattr(sys, "_freelab_tabs_settings_held", None)
    if held is None:
        held = sys._freelab_tabs_settings_held = []
    return held


def let_go(dialog, parented):
    """A closed settings dialog, deleted once by Qt (deleteLater from a plain timer's slot, never from
    inside its own signals) when it has FontLab's main window as its parent, which PythonQt leaves to Qt.
    A parentless one (no main window found) is kept, hidden: PythonQt deletes a widget made from Python
    the moment its last reference goes."""
    from PythonQt.QtCore import QTimer
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
    """The settings dialog, modal; the settings saved (None on Cancel). The dialog has FontLab's main
    window as its parent and is deleted once closed (let_go)."""
    from PythonQt.QtGui import QDialog
    tabs = tabs_module()
    main = main_window()
    dialog = QDialog(main) if main is not None else QDialog()  # (a parent: PythonQt leaves it to Qt)
    try:
        return _run(dialog, tabs)
    finally:
        let_go(dialog, main is not None)


def _run(dialog, tabs):
    from PythonQt.QtGui import QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLabel
    from PythonQt.QtCore import Qt
    chosen = tabs.options(tabs.load_settings())
    dialog.setWindowTitle("FreeLab Tab Docking")
    # FreeLab's own dialog, not a question of FontLab's, for FreeLab MCP's window tools (its mcpScriptWindow
    # convention: a Qt property nothing else reads)
    dialog.setProperty(SCRIPT_WINDOW_PROP, True)
    # No "?" in the title bar: it offered help this dialog does not have.
    flags = int(dialog.windowFlags()) if callable(dialog.windowFlags) else int(dialog.windowFlags)
    dialog.setWindowFlags(Qt.WindowFlags(flags & ~int(Qt.WindowContextHelpButtonHint)))
    layout = QVBoxLayout(dialog)
    reorder_box = QCheckBox(REORDER)
    reorder_box.setToolTip(REORDER_TIP)
    reorder_box.setChecked(chosen["reorder"])
    layout.addWidget(reorder_box)
    no_undock_box = QCheckBox(NO_UNDOCK)
    no_undock_box.setToolTip(NO_UNDOCK_TIP)
    no_undock_box.setChecked(chosen["no_undock"])
    layout.addWidget(no_undock_box)
    if not tabs.is_on():
        note = QLabel(OFF_NOTE)
        note.setWordWrap(True)
        layout.addWidget(note)
    row = QHBoxLayout()
    row.addStretch(1)
    ok, cancel = QPushButton("OK"), QPushButton("Cancel")
    ok.setDefault(True)
    row.addWidget(ok)
    row.addWidget(cancel)
    layout.addLayout(row)
    ok.connect("clicked()", dialog.accept)
    cancel.connect("clicked()", dialog.reject)
    if not dialog.exec_():
        return None
    reorder, no_undock = bool(reorder_box.isChecked()), bool(no_undock_box.isChecked())
    result = tabs.configure(enabled=reorder or no_undock, reorder=reorder, no_undock=no_undock)
    print(tabs.summary(tabs.options(result), on=bool(result.get("enabled"))))
    return result


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_tabs_settings":
    show_dialog()

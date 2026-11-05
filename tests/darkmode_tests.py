# -*- coding: utf-8 -*-
"""Dark-mode tests against fake PythonQt modules; they run under Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "darkmode"))
os.environ["FREELAB_NO_AUTOSTART"] = "1"

import qtfakes  # noqa: E402
import freelab_dark_mode as dm  # noqa: E402


class DarkModeCase(unittest.TestCase):
    placeholder = True

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="freelab-dark-")
        self._old_state = os.environ.get("FREELAB_STATE_DIR")
        os.environ["FREELAB_STATE_DIR"] = self.tmp
        if hasattr(sys, "_freelab_dark_mode"):
            del sys._freelab_dark_mode
        self.app = qtfakes.install(remove_placeholder=not self.placeholder)
        self.original = (self.app.style().objectName(), self.app.palette(), self.app.styleSheet())

    def tearDown(self):
        qtfakes.uninstall()
        if hasattr(sys, "_freelab_dark_mode"):
            del sys._freelab_dark_mode
        if self._old_state is None:
            os.environ.pop("FREELAB_STATE_DIR", None)
        else:
            os.environ["FREELAB_STATE_DIR"] = self._old_state
        shutil.rmtree(self.tmp, ignore_errors=True)

    def current(self):
        return (self.app.style().objectName(), self.app.palette(), self.app.styleSheet())

    def settings(self):
        with open(os.path.join(self.tmp, "darkmode.json")) as handle:
            return json.load(handle)


class ToggleTests(DarkModeCase):
    def test_toggle_on_applies_fusion_palette_and_sheet(self):
        self.assertTrue(dm.toggle())
        style, palette, sheet = self.current()
        self.assertEqual(style, "Fusion")
        self.assertEqual(palette.colors[("All", "Window")], qtfakes.QColor("#2d2d30"))
        self.assertEqual(palette.colors[("Disabled", "Text")], qtfakes.QColor("#7f7f7f"))
        self.assertTrue(sheet.startswith(self.original[2]), "FontLab's own stylesheet must stay first")
        self.assertIn(dm.STYLESHEET_MARK, sheet)
        self.assertEqual(self.settings(), {"enabled": True})

    def test_toggle_off_restores_everything(self):
        dm.toggle()
        self.assertFalse(dm.toggle())
        self.assertEqual(self.current(), self.original)
        self.assertEqual(self.settings(), {"enabled": False})

    def test_reapplying_does_not_stack_the_stylesheet(self):
        dm.apply_dark()
        dm.apply_dark()
        dm.apply_dark()
        self.assertEqual(self.app.styleSheet().count(dm.STYLESHEET_MARK), 1)
        dm.restore()
        self.assertEqual(self.current(), self.original)

    def test_restore_keeps_fontlabs_later_stylesheet_changes(self):
        dm.apply_dark()
        fontlab_change = u"QLabel { color: red; }"
        self.app.setStyleSheet(fontlab_change + u"\n" + self.app.styleSheet())  # FontLab restyles meanwhile
        dm.apply_dark()
        dm.restore()
        style, palette, sheet = self.current()
        self.assertEqual((style, palette), self.original[:2])
        self.assertNotIn(dm.STYLESHEET_MARK, sheet)
        self.assertIn(fontlab_change, sheet)
        self.assertIn(self.original[2], sheet)

    def test_restore_without_apply_is_harmless(self):
        dm.restore()
        self.assertEqual(self.current(), self.original)

    def test_settings_file_other_keys_survive(self):
        with open(os.path.join(self.tmp, "darkmode.json"), "w") as handle:
            json.dump({"enabled": False, "future": 1}, handle)
        dm.toggle()
        self.assertEqual(self.settings(), {"enabled": True, "future": 1})

    def test_bad_settings_file_reads_as_off(self):
        with open(os.path.join(self.tmp, "darkmode.json"), "w") as handle:
            handle.write("[not json")
        dm.startup()
        self.assertEqual(self.current(), self.original)


class StartupTests(DarkModeCase):
    def test_startup_does_nothing_when_off(self):
        dm.startup()
        self.assertEqual(self.current(), self.original)
        self.assertEqual(qtfakes.QTimer.made, [])

    def test_startup_applies_and_reapplies_when_on(self):
        dm.save_settings({"enabled": True})
        dm.startup()
        self.assertEqual(self.app.style().objectName(), "Fusion")
        timers = qtfakes.QTimer.made
        self.assertEqual([t.interval for t in timers], list(dm.REAPPLY_DELAYS_MS))
        self.assertTrue(all(t.single and t.running for t in timers))
        # FontLab puts its own style back after the startup script ran; the timers win it back.
        self.app.setStyle(qtfakes.FakeStyle("windowsvista"))
        timers[1].fire()
        self.assertEqual(self.app.style().objectName(), "Fusion")

    def test_toggling_off_cancels_pending_reapply(self):
        dm.save_settings({"enabled": True})
        dm.startup()
        dm.toggle()
        self.assertTrue(all(not t.running for t in qtfakes.QTimer.made))
        self.assertEqual(self.current(), self.original)


class OldQtTests(DarkModeCase):
    placeholder = False

    def test_missing_palette_role_is_skipped(self):
        dm.apply_dark()
        roles = set(role for _group, role in self.app.palette().colors)
        self.assertNotIn("PlaceholderText", roles)
        self.assertIn("Window", roles)


if __name__ == "__main__":
    unittest.main()

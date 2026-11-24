# -*- coding: utf-8 -*-
"""windows/freelab_setup.py: Scripts > FreeLab > Set Up FreeLab, on fixture files (Python 2.7 and 3).

Nothing of FontLab's is touched: the startup script and the tools folder are temporary files.
"""

from __future__ import absolute_import, division, print_function

import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "windows"))
import freelab_setup as fs  # noqa: E402

MINE = u"import fontlab\nprint('mine')\n"
MCP = u"# >>> FreeLab MCP (managed by FreeLab MCP tools/install-fontlab.ps1; -Uninstall removes it)\nmcp = 1\n# <<< FreeLab MCP\n"


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="freelab-setup-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.folder = os.path.join(self.tmp, u"Scripts", u"FreeLab")
        os.makedirs(self.folder)
        for name in fs.TOOLS:
            io.open(os.path.join(self.folder, name), "wb").close()
        self.startup = os.path.join(self.tmp, u"startupScript.py")
        self.said, self.answers = [], []

    def write(self, text, bom=False, crlf=False):
        if crlf:
            text = text.replace(u"\n", u"\r\n")
        with io.open(self.startup, "wb") as handle:
            handle.write((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))

    def read(self, path=None):
        with io.open(path or self.startup, "rb") as handle:
            return handle.read()

    def run_main(self, answer=True):
        def ask(text, yes, no):
            self.answers.append((text, yes, no))
            return answer
        return fs.main(self.said.append, ask, self.startup, self.folder)

    def test_the_block_is_the_installers_to_the_letter(self):
        """One block, whoever writes it: a later install by tools/install-fontlab.ps1 finds it up to date."""
        installer = os.path.join(ROOT, "tools", "install-fontlab.ps1")
        if not os.path.isfile(installer):
            self.skipTest("the installer is not in this copy (the Python 2.7 run)")
        with io.open(installer, encoding="utf-8") as handle:
            text = handle.read().replace(u"\r\n", u"\n")
        first = text.index(u'$block = @"\n') + len(u'$block = @"\n')
        self.assertEqual(fs.BLOCK, text[first:text.index(u'\n"@', first)])
        self.assertIn(u"$begin = '%s'" % fs.BEGIN, text)
        self.assertIn(u"$end = '%s'" % fs.END, text)

    def test_paths_are_written_as_ascii_literals(self):
        self.assertEqual(fs.py_literal(u'C:\\Users\\\u540d "x"\\a'), u'u"C:\\\\Users\\\\\\u540d \\"x\\"\\\\a"')
        made = fs.block(u"C:\\Docs\\Scripts\\FreeLab")
        self.assertIn(u'u"C:\\\\Docs\\\\Scripts\\\\FreeLab\\\\freelab_dark_mode.py"', made)
        self.assertNotIn(u"$", made)
        made.encode("ascii")
        compile(made, "block", "exec")  # (it is Python)

    def test_setting_up_adds_the_block_and_keeps_the_original(self):
        self.write(MINE + MCP)
        self.assertEqual(fs.state(self.startup, self.folder)[0], "absent")
        self.assertTrue(fs.set_up(self.startup, self.folder))
        text = self.read().decode("utf-8")
        self.assertTrue(text.startswith(MINE + MCP), "the user's code and FreeLab MCP's block as they were")
        self.assertTrue(text.endswith(fs.END + u"\n"))
        self.assertEqual(self.read(self.startup + ".freelab-backup").decode("utf-8"), MINE + MCP)
        self.assertEqual(fs.state(self.startup, self.folder)[0], "current")
        self.assertFalse(fs.set_up(self.startup, self.folder), "again: nothing to change")
        self.assertFalse(os.path.exists(self.startup + ".freelab-new"))

    def test_line_ends_and_the_byte_order_mark_are_kept(self):
        self.write(MINE, bom=True, crlf=True)
        fs.set_up(self.startup, self.folder)
        data = self.read()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        fs.remove(self.startup, self.folder)
        self.assertEqual(self.read(), (b"\xef\xbb\xbf" + MINE.replace(u"\n", u"\r\n").encode("utf-8")))

    def test_an_older_block_is_replaced_where_it_is(self):
        old = fs.BEGIN + u" (an earlier one)\nold = 1\n" + fs.END + u"\n"
        self.write(MINE + old + MCP)
        self.assertEqual(fs.state(self.startup, self.folder)[0], "outdated")
        fs.set_up(self.startup, self.folder)
        text = self.read().decode("utf-8")
        self.assertNotIn(u"old = 1", text)
        self.assertTrue(text.index(fs.BEGIN) < text.index(u"# >>> FreeLab MCP"), "in its place, before FreeLab MCP's")
        self.assertEqual(self.read(self.startup + ".freelab-previous").decode("utf-8"), MINE + old + MCP)

    def test_removing_takes_out_the_block_alone(self):
        self.write(MINE + MCP)
        fs.set_up(self.startup, self.folder)
        self.assertTrue(fs.remove(self.startup, self.folder))
        self.assertEqual(self.read().decode("utf-8"), MINE + MCP)
        self.assertFalse(fs.remove(self.startup, self.folder))

    def test_a_file_that_cannot_be_changed_safely_is_left_as_it_is(self):
        cases = [(MINE.encode("utf-8") + b"caf\xe9 = 1\n", fs.NOT_UTF8),
                 ((MINE + fs.BEGIN + u"\nx = 1\n").encode("utf-8"), fs.UNPAIRED),
                 ((fs.END + u"\n" + fs.BEGIN + u"\n").encode("utf-8"), fs.UNPAIRED),
                 ((fs.BEGIN + u"\n# <<< FreeLab MCP\n").encode("utf-8"), fs.UNPAIRED)]
        for data, why in cases:
            with io.open(self.startup, "wb") as handle:
                handle.write(data)
            self.said[:] = []
            self.assertEqual(self.run_main(), "refused")
            self.assertEqual(self.said, [why])
            self.assertEqual(self.read(), data)
            self.assertFalse(os.path.exists(self.startup + ".freelab-backup"))
        os.remove(self.startup)
        self.said[:] = []
        self.assertEqual(self.run_main(), "refused")
        self.assertEqual(self.said, [fs.NO_STARTUP])

    def test_marker_text_inside_the_users_code_is_no_marker(self):
        mine = u'note = "%s"\n    %s\n' % (fs.BEGIN, fs.END)
        self.write(mine)
        fs.set_up(self.startup, self.folder)
        fs.remove(self.startup, self.folder)
        self.assertEqual(self.read().decode("utf-8"), mine)

    def test_tools_missing_beside_the_script_refuse_the_setup(self):
        self.write(MINE)
        os.remove(os.path.join(self.folder, "freelab_tabs.py"))
        self.assertEqual(self.run_main(), "refused")
        self.assertIn(u"freelab_tabs.py is not in", self.said[0])
        self.assertEqual(self.read().decode("utf-8"), MINE)

    def test_main_sets_up_then_offers_to_remove(self):
        self.write(MINE)
        started = []
        saved = fs.start_now
        fs.start_now = started.append
        self.addCleanup(setattr, fs, "start_now", saved)
        self.assertEqual(self.run_main(), "set up")
        self.assertEqual((self.said, started, self.answers), ([fs.SET_UP_DONE], [self.folder], []))
        self.assertEqual(self.run_main(answer=False), "kept")
        self.assertEqual(self.answers, [(fs.ASK_REMOVE, u"Remove", u"Keep")])
        self.assertIn(fs.BEGIN, self.read().decode("utf-8"))
        holder = getattr(sys, "_freelab_dark_mode", None)
        sys._freelab_dark_mode = {"on": True}
        try:
            self.said[:] = []
            self.assertEqual(self.run_main(), "refused")
            self.assertEqual(self.said, [fs.DARK_FIRST], "dark mode on: FontLab's own colors first")
            sys._freelab_dark_mode = {"on": False}
            self.assertEqual(self.run_main(), "removed")
        finally:
            sys._freelab_dark_mode = holder
        self.assertEqual(self.read().decode("utf-8"), MINE)
        self.assertEqual(self.said[-1], fs.REMOVED)


class NativeLibraryPathTests(unittest.TestCase):
    """The native libraries a release ships beside the scripts are found where the installer built none."""

    def paths(self, finder):
        tmp = tempfile.mkdtemp(prefix="freelab-native-")
        self.addCleanup(shutil.rmtree, tmp, True)
        built = os.path.join(tmp, "state", "bin", "lib-v1.dll")
        here = os.path.join(tmp, "Scripts", "FreeLab")
        beside = os.path.join(here, "bin", "lib-v1.dll")
        self.assertEqual(finder(built, "lib-v1.dll", here), built, "neither: where the installer builds it")
        os.makedirs(os.path.dirname(beside))
        io.open(beside, "wb").close()
        self.assertEqual(finder(built, "lib-v1.dll", here), beside, "the release's own")
        os.makedirs(os.path.dirname(built))
        io.open(built, "wb").close()
        self.assertEqual(finder(built, "lib-v1.dll", here), built, "the one built here comes first")

    def test_dark_modes_helper(self):
        sys.path.insert(0, os.path.join(ROOT, "darkmode"))
        self.addCleanup(sys.path.remove, os.path.join(ROOT, "darkmode"))
        import freelab_dark_mode
        self.paths(freelab_dark_mode._built_or_beside)

    def test_the_kerning_core(self):
        sys.path.insert(0, os.path.join(ROOT, "kerning"))
        self.addCleanup(sys.path.remove, os.path.join(ROOT, "kerning"))
        import freelab_auto_kerning
        self.paths(freelab_auto_kerning.built_or_beside)
        self.assertIn(u"Set Up FreeLab", freelab_auto_kerning.menu_order([u"Set Up FreeLab", u"Proof"]))
        self.assertEqual(freelab_auto_kerning.menu_order([u"Set Up FreeLab", u"Start MCP Listener", u"Proof"]),
                         [u"Proof", None, u"Start MCP Listener", None, u"Set Up FreeLab"])


if __name__ == "__main__":
    unittest.main()

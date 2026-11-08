"""tools/install-fontlab.ps1 run on fixture files: the startup script's blocks, encoding, and line endings (Python 3, Windows).

The installer runs in Windows PowerShell with every location redirected to a temporary folder and
the native helper already "built" there; nothing of FontLab's is touched. Skipped where Windows
PowerShell is missing.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "tools" / "install-fontlab.ps1"
POWERSHELL = shutil.which("powershell.exe") if sys.platform == "win32" else None
NO_WINDOW = 0x08000000
VERSION = re.search(r"#define FREELAB_PIXELS_VERSION (\d+)", (ROOT / "darkmode" / "native" / "freelab_pixels.c").read_text()).group(1)
HOOKS = re.search(r"#define FREELAB_HOOKS_VERSION (\d+)", (ROOT / "darkmode" / "native" / "freelab_hooks.c").read_text()).group(1)
KERN = re.search(r"#define FREELAB_KERN_VERSION (\d+)", (ROOT / "kerning" / "native" / "freelab_kern.c").read_text()).group(1)

LEGACY = b"# >>> FreeLab (managed by FreeLab tools/install-fontlab.ps1; -Uninstall removes it)\ndef _freelab_startup():\n    pass\n# <<< FreeLab\n"
MCP = b"# >>> FreeLab MCP (managed by FreeLab MCP tools/install-fontlab.ps1; -Uninstall removes it)\nmcp = 1\n# <<< FreeLab MCP\n"
MINE = b"import fontlab\nprint('mine')\n"


@unittest.skipIf(POWERSHELL is None, "Windows PowerShell is not available")
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="freelab-installer-"))
        self.scripts = self.tmp / "Scripts"
        self.startup = self.tmp / "startupScript.py"
        self.bin = self.tmp / "bin"
        self.state = self.tmp / "state"
        for folder in (self.scripts / "FreeLab", self.bin, self.state / "cache" / "images-old"):
            folder.mkdir(parents=True)
        (self.bin / ("freelab_pixels-v%s.dll" % VERSION)).write_bytes(b"")  # present: nothing is built
        (self.bin / ("freelab_hooks-v%s-%s.dll" % (HOOKS, VERSION))).write_bytes(b"")
        (self.bin / "freelab_pixels-v1.dll").write_bytes(b"")
        (self.bin / "freelab_hooks-v1-1.dll").write_bytes(b"")
        (self.bin / ("freelab_kern-v%s.dll" % KERN)).write_bytes(b"")
        (self.bin / "freelab_kern-v0.dll").write_bytes(b"")
        (self.state / "darkmode.log").write_text("log")
        (self.state / "kerning-cache").mkdir()
        (self.state / "kerning-cache" / "0123.json").write_text("{}")
        (self.state / "listener.json").write_text("{}")  # FreeLab MCP's: never touched here

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_installer(self, *flags):
        proc = subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(INSTALLER),
             "-ScriptsDir", str(self.scripts), "-StartupScript", str(self.startup), "-BinDir", str(self.bin),
             "-StateDir", str(self.state), "-RegistryKey", r"HKCU:\Software\FreeLabInstallerTestNone",
             "-ProcessName", "freelab-no-such-process", *flags],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW,
            timeout=120,
        )
        return proc.returncode, proc.stdout + proc.stderr

    def write(self, data):
        self.startup.write_bytes(data)

    def read(self):
        return self.startup.read_bytes()

    def test_install_replaces_the_legacy_block_and_keeps_the_rest(self):
        self.write(b"\xef\xbb\xbf" + (MINE + LEGACY + MCP).replace(b"\n", b"\r\n"))
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        data = self.read()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"), "the BOM is kept")
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""), "CRLF line endings are kept")
        text = data[3:].replace(b"\r\n", b"\n")
        self.assertTrue(text.startswith(MINE), "the user's code is kept")
        self.assertNotIn(b"# >>> FreeLab (managed", text)
        self.assertIn(MCP, text, "the other repository's block is kept")
        self.assertEqual(text.count(b"# >>> FreeLab tools"), 1)
        self.assertIn("combined FreeLab block", out)
        self.assertFalse((self.bin / "freelab_pixels-v1.dll").exists(), "a superseded helper is retired")
        self.assertFalse((self.bin / "freelab_hooks-v1-1.dll").exists(), "and a superseded native engine")
        self.assertTrue((self.bin / ("freelab_hooks-v%s-%s.dll" % (HOOKS, VERSION))).exists())
        self.assertFalse((self.bin / "freelab_kern-v0.dll").exists(), "and a superseded auto kerning core")
        self.assertTrue((self.bin / ("freelab_kern-v%s.dll" % KERN)).exists())
        self.assertTrue((self.scripts / "FreeLab" / "freelab_auto_kerning.py").exists(), "Auto Kerning is in the FreeLab submenu")
        self.assertTrue((self.scripts / "FreeLab" / "common_pairs.txt").exists(), "with its list of common pairs")
        self.assertTrue((self.scripts / "FreeLab" / "learned_model.json").exists(), "and its learned model")
        self.assertTrue((self.scripts / "FreeLab" / "class_model.json").exists(), "and its class model")
        before = self.read()
        code, out = self.run_installer()
        self.assertEqual((code, self.read()), (0, before), "a second install changes nothing")

    def test_block_is_updated_where_it_is(self):
        self.write(MINE + b"# >>> FreeLab tools (managed)\nold = 1\n# <<< FreeLab tools\n" + MCP)
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        text = self.read()
        self.assertNotIn(b"old = 1", text)
        self.assertTrue(text.startswith(MINE) and text.endswith(MCP), "both blocks keep their order")

    def test_uninstall_removes_only_its_own(self):
        self.write(MINE + MCP)
        self.assertEqual(self.run_installer()[0], 0)
        (self.scripts / "FreeLab" / "freelab_listener.py").write_text("other")
        code, out = self.run_installer("-Uninstall")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read(), MINE + MCP)
        self.assertEqual(sorted(p.name for p in (self.scripts / "FreeLab").iterdir()), ["freelab_listener.py"])
        self.assertFalse((self.state / "cache").exists())
        self.assertFalse((self.state / "darkmode.log").exists())
        self.assertFalse((self.state / "kerning-cache").exists(), "Auto Kerning's remembered analyses go too")
        self.assertTrue((self.state / "listener.json").exists(), "FreeLab MCP's state stays")

    def test_uninstall_without_a_block_leaves_the_file_alone(self):
        self.write(MINE + MCP)
        code, out = self.run_installer("-Uninstall")
        self.assertEqual((code, self.read()), (0, MINE + MCP), out)
        self.assertNotIn("Removed the FreeLab tools block", out)

    def test_block_replaced_in_place_is_whole_even_with_a_dollar_in_the_path(self):
        self.scripts = self.tmp / "Scripts $& $1"
        (self.scripts / "FreeLab").mkdir(parents=True)
        self.write(MINE + b"# >>> FreeLab tools (managed)\nold = 1\n# <<< FreeLab tools\n" + MCP)
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        text = self.read()
        self.assertEqual(text.count(b"# >>> FreeLab tools"), 1)
        self.assertIn(b"_freelab_tools_startup()", text)
        self.assertIn(b"Scripts $& $1", text, "the path is written as it is")

    def test_a_duplicated_block_becomes_one(self):
        block = b"# >>> FreeLab tools (managed)\nold = 1\n# <<< FreeLab tools\n"
        self.write(MINE + block + MCP + block)
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read().count(b"# >>> FreeLab tools"), 1)

    def test_markers_in_the_wrong_order_are_refused(self):
        data = MINE + b"# <<< FreeLab tools\nmine = 2\n# >>> FreeLab tools (managed)\nmine = 3\n"
        self.write(data)
        code, out = self.run_installer()
        self.assertEqual((code, self.read()), (1, data), out)

    def test_removing_a_block_at_the_top_leaves_no_blank_line(self):
        self.write(b"# >>> FreeLab tools (managed)\nold = 1\n# <<< FreeLab tools\n" + MINE)
        code, out = self.run_installer("-Uninstall")
        self.assertEqual((code, self.read()), (0, MINE), out)

    def test_an_unchanged_file_is_not_rewritten(self):
        self.write(MINE + MCP)
        self.assertEqual(self.run_installer()[0], 0)
        before = self.startup.stat().st_mtime_ns
        os.utime(self.startup, ns=(before - 10 ** 9, before - 10 ** 9))
        stamp = self.startup.stat().st_mtime_ns
        self.assertEqual(self.run_installer()[0], 0)
        self.assertEqual(self.startup.stat().st_mtime_ns, stamp)

    def test_non_utf8_file_without_markers_is_left_alone(self):
        data = b"# -*- coding: cp1252 -*-\n# caf\xe9\n"
        self.write(data)
        code, out = self.run_installer()
        self.assertEqual((code, self.read()), (1, data), "the block cannot be added: " + out)
        code, out = self.run_installer("-Uninstall")
        self.assertEqual((code, self.read()), (0, data), out)

    def test_unpaired_marker_is_refused(self):
        data = MINE + b"# >>> FreeLab tools (managed)\nuser = 1\n"
        self.write(data)
        code, out = self.run_installer()
        self.assertEqual((code, self.read()), (1, data), out)

    def test_non_utf8_file_is_refused(self):
        data = b"# caf\xe9\n"
        self.write(data)
        code, out = self.run_installer()
        self.assertEqual((code, self.read()), (1, data), out)

    def test_missing_startup_script_is_not_created(self):
        code, out = self.run_installer()
        self.assertEqual(code, 1, out)
        self.assertFalse(self.startup.exists(), "FontLab writes its own first")


if __name__ == "__main__":
    unittest.main()

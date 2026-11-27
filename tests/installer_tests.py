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
# Font Check's font, five files; the repository holds the first alone, each release publishes the four
# others beside it, and the tools work without them, as does the installer.
FONT_FILES = ["FreeLang-Essential.ttf", "FreeLang-CJK.ttf", "FreeLangPlus-General.ttf",
              "FreeLangPlus-Mongolian-Tibetan.ttf", "FreeLangPlus-Duployan.ttf"]
OPTIONAL_FONTS = FONT_FILES[1:]
OPTIONAL_FONT = "FreeLangPlus-Duployan.ttf"  # (the one a test leaves out of its copy)


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
        self.assertTrue((self.scripts / "FreeLab" / "freelab_kerning_check.py").exists(), "Kerning Check beside it")
        self.assertTrue((self.scripts / "FreeLab" / "freelab_auto_spacing.py").exists(), "and Auto Spacing")
        self.assertTrue((self.scripts / "FreeLab" / "freelab_glyph_compose.py").exists(), "and Glyph Compose")
        self.assertTrue((self.scripts / "FreeLab" / "mark_model.json").exists(), "with its mark model")
        self.assertTrue((self.scripts / "FreeLab" / "glyph_names.json").exists(), "and Glyphs' glyph names")
        self.assertTrue((self.scripts / "FreeLab" / "GlyphData_LICENSE").exists(), "with their notice")
        self.assertTrue((self.scripts / "FreeLab" / "freelab_feature_code.py").exists(), "and Feature Code")
        self.assertTrue((self.scripts / "FreeLab" / "freelab_family_audit.py").exists(), "and Family Audit")
        self.assertTrue((self.scripts / "FreeLab" / "freelab_font_compare.py").exists(), "with Font Compare, whose code it reads")
        self.assertTrue((self.scripts / "FreeLab" / "freelab_cjk_spacing.py").exists(), "and CJK Spacing")
        self.assertTrue((self.scripts / "FreeLab" / "palt_model.json").exists(), "with its trims")
        self.assertTrue((self.scripts / "FreeLab" / "hangul_model.json").exists(), "and its Hangul widths")
        self.assertTrue((self.scripts / "FreeLab" / "freelab_cjk_vertical.py").exists(), "and CJK Vertical")
        self.assertTrue((self.scripts / "FreeLab" / "vertical_model.json").exists(), "with its vertical forms")
        self.assertEqual((self.scripts / "FreeLab" / "add_vertical_metrics.module").read_bytes(),
                         (ROOT / "tools" / "add_vertical_metrics.py").read_bytes(), "and its export step, no menu item")
        self.assertTrue((self.scripts / "FreeLab" / "anchor_model.json").exists(), "and Glyph Compose's anchors")
        self.assertTrue((self.scripts / "FreeLab" / "ligature_model.json").exists(), "the corpus's ligatures")
        self.assertTrue((self.scripts / "FreeLab" / "reference_model.json").exists(), "and its references' spacing")
        self.assertEqual((self.scripts / "FreeLab" / "freelab_tabs_settings.py").read_bytes(),
                         (ROOT / "windows" / "freelab_tabs_settings.py").read_bytes(),
                         "Tab Docking Settings beside Tab Docking, which it loads")
        before = self.read()
        code, out = self.run_installer()
        self.assertEqual((code, self.read()), (0, before), "a second install changes nothing")

    def test_the_block_starts_freelab_once_a_session(self):
        # Live: the startup script ran again as each FreeLab tool opened (FreeLab MCP's listener started
        # over each time); dark mode's startup, the menu hook, and tab docking must not start over
        self.write(b"x = 1\n")
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        folder = self.scripts / "FreeLab"
        for name, call in (("freelab_dark_mode.py", "startup"), ("freelab_auto_kerning.py", "hook_menu_order_soon"),
                           ("freelab_tabs.py", "startup")):
            (folder / name).write_text("import sys\n\ndef %s():\n    sys.started.append(%r)\n\nhook_menu_order = %s\n"
                                       % (call, name, call))
        script = ("import sys\nsys.started = []\nsource = open(%r, encoding='utf-8-sig').read()\n"
                  "for run in range(3):\n    exec(compile(source, 'startupScript.py', 'exec'), {})\n"
                  "print(sorted(sys.started))\n" % str(self.startup))
        done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, errors="replace",
                              creationflags=NO_WINDOW, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        # dark mode and tab docking once; the menu's order hooked each time (Refresh Scripts builds the menu
        # anew and runs the startup script again; the hook does nothing on a menu it has hooked)
        self.assertEqual(done.stdout.strip(),
                         "['freelab_auto_kerning.py', 'freelab_auto_kerning.py', 'freelab_auto_kerning.py', "
                         "'freelab_dark_mode.py', 'freelab_tabs.py']")

    def test_only_scripts_with_a_menu_title_are_installed_as_py(self):
        """FontLab lists every .py of the folder in Scripts > FreeLab: a helper module went in as
        freelab_alternates.py and showed there as "Freelab_alternates"."""
        self.write(MINE)
        old = self.scripts / "FreeLab" / "freelab_alternates.py"
        old.write_text("old = 1\n")
        (self.scripts / "FreeLab" / "freelab_alternates.pyc").write_bytes(b"old")
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        folder = self.scripts / "FreeLab"
        self.assertFalse(old.exists(), "the helper once installed as a script is removed")
        self.assertFalse((folder / "freelab_alternates.pyc").exists(), "with its compiled copy")
        self.assertEqual((folder / "freelab_alternates.module").read_bytes(),
                         (ROOT / "features" / "freelab_alternates.py").read_bytes())
        untitled = [path.name for path in folder.glob("*.py")
                    if not path.read_bytes().lstrip(b"\xef\xbb\xbf").startswith(b"#FLM:")]
        self.assertEqual(untitled, [], "every installed .py names its menu entry")

    def test_diacritics_gives_way_to_glyph_compose(self):
        """Diacritics was renamed Glyph Compose: its installed script (and a compiled copy) go, so the menu
        lists the tool once, and its Glyph generation tab goes in as a helper with its table and notice."""
        self.write(MINE)
        folder = self.scripts / "FreeLab"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "freelab_diacritics.py").write_text("#FLM: Diacritics\n")
        (folder / "freelab_diacritics.pyc").write_bytes(b"old")
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        self.assertFalse((folder / "freelab_diacritics.py").exists(), out)
        self.assertFalse((folder / "freelab_diacritics.pyc").exists())
        self.assertIn("Removed the retired", out)
        self.assertTrue((folder / "freelab_glyph_compose.py").read_bytes().startswith(b"#FLM: Glyph Compose"))
        self.assertEqual((folder / "freelab_glyph_generation.module").read_bytes(),
                         (ROOT / "compose" / "freelab_glyph_generation.py").read_bytes())
        self.assertFalse((folder / "freelab_glyph_generation.py").exists(), "a helper: no menu entry")
        for name in ("glyph_generation.json", "glyph_generation_LICENSE"):
            self.assertEqual((folder / name).read_bytes(), (ROOT / "compose" / name).read_bytes(), name)
        code, out = self.run_installer("-Uninstall")
        self.assertEqual(code, 0, out)
        self.assertFalse((folder / "freelab_glyph_generation.module").exists())

    def test_the_font_under_its_earlier_names_is_removed(self):
        """Font Check's font was FreeLabAutonyms.ttf, then FreeLabLanguages.ttf, then one FreeLang.ttf,
        then three files, and is five: an install puts the five and their license in and removes the
        earlier ones (FreeLang-Extended.ttf, the third of three, among them), and one FontLab holds
        open (it registered the font) is reported and left, the install going on."""
        self.write(MINE)
        folder = self.scripts / "FreeLab"
        earlier = ("FreeLabAutonyms.ttf", "FreeLabAutonyms_LICENSE", "FreeLabLanguages.ttf", "FreeLabLanguages_LICENSE",
                   "FreeLang.ttf", "FreeLang-Extended.ttf", "FreeLang-Extended-General.ttf",
                   "FreeLang-Extended-Mongolian-Tibetan.ttf", "FreeLang-Extended-Duployan.ttf")  # (then FreeLang+)
        for name in earlier:
            (folder / name).write_bytes(b"old")
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        self.assertEqual([name for name in earlier if (folder / name).exists()], [], out)
        self.assertIn("Removed the retired", out)
        fonts = [name for name in FONT_FILES if (ROOT / "checks" / "language_font" / name).exists()]
        self.assertEqual([name for name in FONT_FILES if name not in fonts and name not in OPTIONAL_FONTS], [],
                         "only an optional font may be absent from a copy of the repository")
        for name in fonts + ["FreeLang_LICENSE"]:
            self.assertEqual((folder / name).read_bytes(), (ROOT / "checks" / "language_font" / name).read_bytes(), name)
        self.assertEqual(sorted(path.name for path in folder.glob("FreeLang*.ttf")), sorted(fonts))
        held = folder / "FreeLabLanguages.ttf"
        held.write_bytes(b"old")
        with open(str(held), "rb"):  # (opened without sharing deletion, as a registered font is)
            code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        self.assertTrue(held.exists(), "in use: left where it is")
        self.assertIn("Could not remove the retired", out)
        self.assertIn("the next install removes it", out)
        self.assertIn("Left for the next install", out, "a font FontLab holds: expected, the status stays 0")
        self.assertIn("tools block", out, "the rest of the install went on")
        code, out = self.run_installer("-Uninstall")
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(p.name for p in folder.parent.glob("FreeLab/*")), [], "an uninstall removes it too")

    def test_the_optional_font_may_be_absent(self):
        """The installer lists the five fonts, in ASCII names, and marks all but Essential optional:
        run from a copy of the repository without one (here, Duployan's), it installs the others,
        says it skipped the one, and leaves an installed copy of it alone."""
        text = INSTALLER.read_text(encoding="ascii")  # (an ASCII-only script: read in the system code page)
        listed = re.findall(r"From = '([^']+)'; Name = '([^']+)'(; Optional = \$true)?", text)
        self.assertEqual([name for _, name, _ in listed if name.endswith(".ttf")], FONT_FILES)
        self.assertEqual([name for _, name, optional in listed if optional], OPTIONAL_FONTS)
        self.assertIn("'FreeLang-Extended.ttf'", text, "retired")
        copy = self.tmp / "copy"
        for relative in [found[0] for found in listed] + ["tools\\install-fontlab.ps1"] + [
                str(path.relative_to(ROOT)) for folder in ("darkmode/native", "kerning/native") for path in (ROOT / folder).glob("*.c")]:
            if relative.endswith(OPTIONAL_FONT) or not (ROOT / Path(*relative.split("\\"))).exists():
                continue  # (and an optional font this copy of the repository lacks)
            target = copy / Path(*relative.split("\\"))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(ROOT / Path(*relative.split("\\"))), str(target))
        self.write(MINE)
        folder = self.scripts / "FreeLab"
        (folder / OPTIONAL_FONT).write_bytes(b"installed earlier")
        installer = copy / "tools" / "install-fontlab.ps1"
        proc = subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(installer),
             "-ScriptsDir", str(self.scripts), "-StartupScript", str(self.startup), "-BinDir", str(self.bin),
             "-StateDir", str(self.state), "-RegistryKey", r"HKCU:\Software\FreeLabInstallerTestNone",
             "-ProcessName", "freelab-no-such-process"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW)
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, out)
        self.assertIn("Skipped %s (optional, not in this copy)" % OPTIONAL_FONT, out)
        self.assertEqual((folder / OPTIONAL_FONT).read_bytes(), b"installed earlier")
        for name in FONT_FILES[:-1]:
            if (ROOT / "checks" / "language_font" / name).exists():
                self.assertEqual((folder / name).read_bytes(), (ROOT / "checks" / "language_font" / name).read_bytes(), name)

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

    def test_uninstall_removes_the_window_size_and_proof_settings(self):
        self.write(MINE)
        self.assertEqual(self.run_installer()[0], 0)
        (self.state / "windows.json").write_text('{"size": [900, 700]}')
        (self.state / "proof.json").write_text('{"summary": false}')
        code, out = self.run_installer("-Uninstall")
        self.assertEqual(code, 0, out)
        self.assertFalse((self.state / "windows.json").exists(), out)
        self.assertFalse((self.state / "proof.json").exists(), out)
        self.assertTrue((self.state / "listener.json").exists(), "FreeLab MCP's state stays")

    def test_the_scripts_folder_itself_loses_only_what_freelab_put_there(self):
        """Before 0.3 FreeLab installed dark mode's two scripts in the Scripts folder itself: those go, on
        install and uninstall. A file of the same name as one FreeLab installs now in its submenu
        (character_sets.json and the like, generic names) is the user's: kept. A locked old script is a
        reported skip, the install going on."""
        self.write(MINE)
        theirs = ["character_sets.json", "language_families.json", "language_orthographies.json",
                  "language_orthographies_LICENSE", "freelab_proof.py", "common_pairs.txt"]
        for name in theirs:
            (self.scripts / name).write_text("the user's own")
        old = self.scripts / "freelab_dark_mode.py"
        old.write_text("old")
        (self.scripts / "freelab_dark_mode_settings.py").write_text("old")
        with open(str(old), "rb"):  # (opened without sharing deletion: the delete fails)
            code, out = self.run_installer()
        self.assertEqual(code, 1, "an old script left in the menu: not done, said, and the status says so: " + out)
        self.assertIn("Could not remove the old", out)
        self.assertIn("in use by another program", out, "the real reason")
        self.assertIn("Not done (1)", out)
        self.assertIn("tools block", out, "the rest of the install went on")
        self.assertTrue(old.exists())
        self.assertFalse((self.scripts / "freelab_dark_mode_settings.py").exists(), out)
        self.assertEqual([name for name in theirs if not (self.scripts / name).exists()], [], out)
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        self.assertFalse(old.exists(), "no longer locked: removed")
        old.write_text("old")
        code, out = self.run_installer("-Uninstall")
        self.assertEqual(code, 0, out)
        self.assertFalse(old.exists(), "an uninstall removes it too")
        self.assertEqual([name for name in theirs if not (self.scripts / name).exists()], [], out)

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

    # Review of 2026-11-15: the check took markers at the start of a line only, the changes took marker text
    # anywhere, so an install or uninstall deleted the user's code between two quoted markers

    QUOTED = (b'print("# >>> FreeLab tools")\nuser_work()\nprint("# <<< FreeLab tools")\nkeep_me()\n'
              b'text = """\n    # >>> FreeLab tools (indented)\n    middle()\n    # <<< FreeLab tools\n"""\n'
              b'print("# >>> FreeLab (managed")\nlegacy_work()\nprint("# <<< FreeLab")\n')

    def test_marker_text_in_the_users_code_is_kept_byte_for_byte(self):
        original = b"\xef\xbb\xbf" + (MINE + self.QUOTED + MCP).replace(b"\n", b"\r\n")
        self.write(original)
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        data = self.read()
        self.assertTrue(data.startswith(original.rstrip(b"\r\n")), "everything before the new block as it was: " + out)
        self.assertEqual(data.count(b"\n# >>> FreeLab tools (managed by"), 1, "the block appended once")
        self.assertNotIn("combined FreeLab block", out, "quoted legacy markers are not a legacy block")
        code, out = self.run_installer("-Uninstall")
        self.assertEqual((code, self.read()), (0, original), out)

    def test_a_block_between_quoted_markers_is_found_and_replaced_alone(self):
        data = MINE + self.QUOTED + b"# >>> FreeLab tools (managed)\nold = 1\n# <<< FreeLab tools\n" + MCP
        self.write(data)
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        text = self.read()
        self.assertTrue(text.startswith(MINE + self.QUOTED), "the user's code as it was")
        self.assertTrue(text.endswith(MCP))
        self.assertNotIn(b"old = 1", text)
        self.assertEqual(self.run_installer("-Uninstall")[0], 0)
        self.assertEqual(self.read(), MINE + self.QUOTED + MCP)

    def test_a_block_opened_by_one_kind_and_closed_by_another_is_refused(self):
        for data in (MINE + b"# >>> FreeLab tools (managed)\nmine = 1\n# <<< FreeLab MCP\n",
                     MINE + b"# >>> FreeLab MCP (managed)\nmine = 1\n# <<< FreeLab tools\n",
                     MINE + b"# >>> FreeLab (managed)\nmine = 1\n# <<< FreeLab tools\n",
                     MINE + b"# >>> FreeLab tools (managed)\n# >>> FreeLab MCP\nmine = 1\n# <<< FreeLab MCP\n"
                            b"# <<< FreeLab tools\n"):
            self.write(data)
            for flags in ((), ("-Uninstall",)):
                code, out = self.run_installer(*flags)
                self.assertEqual((code, self.read()), (1, data), out)
                self.assertIn("left as it is", out)

    def test_each_update_keeps_the_file_it_replaced(self):
        first = MINE + MCP
        self.write(first)
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        backup = self.tmp / "startupScript.py.freelab-backup"
        previous = self.tmp / "startupScript.py.freelab-previous"
        self.assertEqual(backup.read_bytes(), first, "the first install's copy")
        self.assertEqual(previous.read_bytes(), first)
        edited = self.read() + b"later = 2\n"  # (the user's change after the install)
        self.write(edited)
        code, out = self.run_installer("-Uninstall")
        self.assertEqual(code, 0, out)
        self.assertEqual(previous.read_bytes(), edited, "the file as it was just before this change")
        self.assertEqual(backup.read_bytes(), first, "the first install's copy stays")
        self.assertIn(b"later = 2", self.read())
        self.assertEqual(sorted(p.name for p in self.tmp.glob("startupScript.py*")),
                         ["startupScript.py", "startupScript.py.freelab-backup", "startupScript.py.freelab-previous"],
                         "no temporary file left")

    # Review of 2026-11-15: a required copy that failed was printed and the install went on (retiring old
    # files, writing the block) with exit status 0; uninstall said 0 whatever it left

    def test_a_script_that_cannot_be_replaced_stops_the_install_before_anything_changes(self):
        self.write(MINE)
        self.assertEqual(self.run_installer()[0], 0)
        folder = self.scripts / "FreeLab"
        (folder / "freelab_auto_kerning.py").write_bytes(b"old kerning")
        held = folder / "freelab_auto_spacing.py"
        held.write_bytes(b"old spacing")
        retired = folder / "freelab_accents.py"
        retired.write_bytes(b"retired")
        startup = self.read()
        with open(str(held), "rb"):  # (held open by another program)
            code, out = self.run_installer()
        self.assertEqual(code, 1, out)
        self.assertIn("in use by another program", out)
        self.assertIn("Nothing installed was replaced", out)
        self.assertEqual((folder / "freelab_auto_kerning.py").read_bytes(), b"old kerning", "the earlier set kept whole")
        self.assertEqual(held.read_bytes(), b"old spacing")
        self.assertTrue(retired.exists(), "nothing retired before its replacement is in")
        self.assertEqual(self.read(), startup, "the startup block not touched")
        self.assertEqual(list(folder.glob("*.freelab-new")), [], "the staged copies cleared")
        code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        self.assertEqual(held.read_bytes(), (ROOT / "spacing" / "freelab_auto_spacing.py").read_bytes())
        self.assertFalse(retired.exists())

    def test_a_font_held_open_is_kept_and_the_install_succeeds(self):
        self.write(MINE)
        self.assertEqual(self.run_installer()[0], 0)
        font = self.scripts / "FreeLab" / "FreeLang-Essential.ttf"
        font.write_bytes(b"older font")
        (self.scripts / "FreeLab" / "freelab_auto_kerning.py").write_bytes(b"old kerning")
        with open(str(font), "rb"):  # (FontLab registered it: open until it quits)
            code, out = self.run_installer()
        self.assertEqual(code, 0, out)
        self.assertEqual(font.read_bytes(), b"older font")
        self.assertIn("Left for the next install", out)
        self.assertEqual((self.scripts / "FreeLab" / "freelab_auto_kerning.py").read_bytes(),
                         (ROOT / "kerning" / "freelab_auto_kerning.py").read_bytes(), "the rest installed")

    def test_without_the_auto_kerning_core_the_status_says_so(self):
        copy = self.tmp / "copy"
        for relative in ["tools/install-fontlab.ps1", "darkmode/native/freelab_pixels.c", "darkmode/native/freelab_hooks.c",
                         "kerning/native/freelab_kern.c"]:
            target = copy / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(ROOT / relative), str(target))
        (copy / "tools" / "build-native.ps1").write_text(
            "param([string]$Out, [switch]$Hooks, [switch]$Kern)\nthrow 'No compiler found (test)'\n")
        text = INSTALLER.read_text(encoding="ascii")
        for source, _ in re.findall(r"From = '([^']+)'; Name = '([^']+)'", text):
            if (ROOT / Path(*source.split("\\"))).exists():
                target = copy / Path(*source.split("\\"))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(ROOT / Path(*source.split("\\"))), str(target))
        (self.bin / ("freelab_kern-v%s.dll" % KERN)).unlink()
        self.write(MINE)
        proc = subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
             str(copy / "tools" / "install-fontlab.ps1"), "-ScriptsDir", str(self.scripts), "-StartupScript",
             str(self.startup), "-BinDir", str(self.bin), "-StateDir", str(self.state), "-RegistryKey",
             r"HKCU:\Software\FreeLabInstallerTestNone", "-ProcessName", "freelab-no-such-process"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW,
            timeout=120)
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 1, out)
        self.assertIn("auto kerning core", out)
        self.assertIn("Not done (1)", out)
        self.assertIn(b"# >>> FreeLab tools", self.read(), "dark mode and the rest installed")

    def test_an_uninstall_that_leaves_files_says_so(self):
        self.write(MINE)
        self.assertEqual(self.run_installer()[0], 0)
        held = self.scripts / "FreeLab" / "freelab_proof.py"
        with open(str(held), "rb"):
            code, out = self.run_installer("-Uninstall")
        self.assertEqual(code, 1, out)
        self.assertIn("freelab_proof.py", out.split("Not done")[-1])
        self.assertTrue(held.exists())
        code, out = self.run_installer("-Uninstall")
        self.assertEqual(code, 0, out)
        self.assertFalse(held.exists())

    def test_missing_startup_script_is_not_created(self):
        code, out = self.run_installer()
        self.assertEqual(code, 1, out)
        self.assertFalse(self.startup.exists(), "FontLab writes its own first")


class ReleaseFolderTests(unittest.TestCase):
    """tools/pack_release.py: a release's ready-made FreeLab folder, dropped into FontLab's Scripts folder."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "tools"))
        self.addCleanup(sys.path.remove, str(ROOT / "tools"))
        import pack_release
        self.pack = pack_release
        self.tmp = Path(tempfile.mkdtemp(prefix="freelab-release-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)

    def test_the_folder_holds_what_the_installer_installs_and_what_a_drop_in_needs(self):
        files = self.pack.installed_files()
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertEqual(len(files), text.count("@{ From = "), "every row of the installer's list")
        self.assertIn(("compose/freelab_glyph_generation.py", "freelab_glyph_generation.module", False), files)
        self.assertEqual([name for _s, name, optional in files if optional], OPTIONAL_FONTS)
        self.assertEqual(self.pack.native_names(), ["freelab_pixels-v%s.dll" % VERSION, "freelab_hooks-v%s-%s.dll" % (HOOKS, VERSION),
                                                    "freelab_kern-v%s.dll" % KERN], "the native dark mode engine too")
        for name in self.pack.native_names():
            (self.tmp / name).write_bytes(b"built")
        missing = [source for source, _n, _o in files if not (ROOT / source).is_file()]
        if missing:
            self.skipTest("this copy lacks %s" % ", ".join(missing))
        out = self.tmp / "release.zip"
        size, digest = self.pack.pack(str(out), str(self.tmp))
        again = self.tmp / "again.zip"
        self.assertEqual(self.pack.pack(str(again), str(self.tmp)), (size, digest), "the same files, the same bytes")
        import zipfile
        with zipfile.ZipFile(str(out)) as archive:
            names = archive.namelist()
            notes = archive.read("FreeLab/README.txt").decode("utf-8")
            setup = archive.read("FreeLab/freelab_setup.py")
        self.assertTrue(all(name.startswith("FreeLab/") for name in names), "one folder, unpacked into Scripts")
        self.assertEqual(len(names), len(set(names)))
        for name in ["freelab_auto_kerning.py", "freelab_setup.py", "LICENSE", "README.txt", "FreeLang-CJK.ttf",
                     "bin/freelab_pixels-v%s.dll" % VERSION, "bin/freelab_hooks-v%s-%s.dll" % (HOOKS, VERSION),
                     "bin/freelab_kern-v%s.dll" % KERN]:
            self.assertIn("FreeLab/" + name, names)
        self.assertEqual(setup, (ROOT / "windows" / "freelab_setup.py").read_bytes())
        self.assertIn("FreeLab Script Suite %s," % self.pack.version(), notes)
        self.assertIn("Set Up FreeLab", notes)
        # (only the scripts FontLab should list are .py: a helper listed as a script was the stray entry of November 24)
        listed = sorted(name[len("FreeLab/"):] for name in names if name.endswith(".py"))
        self.assertNotIn("freelab_glyph_generation.py", listed)
        self.assertNotIn("freelab_trace.py", listed)

    def test_a_library_not_built_stops_the_packing(self):
        with self.assertRaises(SystemExit):
            self.pack.entries(str(self.tmp))


if __name__ == "__main__":
    unittest.main()

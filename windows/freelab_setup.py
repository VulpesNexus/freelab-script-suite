#FLM: Set Up FreeLab
# -*- coding: utf-8 -*-
"""FreeLab's setup from inside FontLab, for a copy dropped into the Scripts folder (a release's
FreeLab-Script-Suite zip) with no installer run: Scripts > FreeLab > Set Up FreeLab.

It adds FreeLab's block to FontLab's startup script, the one thing a dropped folder cannot do by itself:
the block arranges Scripts > FreeLab, starts tab docking, and applies dark mode at launch when it was left
on. It is the block tools/install-fontlab.ps1 writes, to the letter (a test compares them), under the same
rules: the startup script is read as strict UTF-8 and written back with its own line endings and byte
order mark, the original is kept as startupScript.py.freelab-backup, each change keeps the file it replaced
as startupScript.py.freelab-previous, and a file that is not UTF-8 or whose FreeLab markers do not pair is
left as it is. Run again once FreeLab is set up, it offers to take the block out.

Valid Python 2.7 (FontLab 7) and Python 3.
"""

from __future__ import absolute_import, division, print_function

import io
import os
import re
import sys

BEGIN, END = u"# >>> FreeLab tools", u"# <<< FreeLab tools"
OWN_OPEN = re.compile(u"^" + re.escape(BEGIN) + u"(?:[ \\t].*)?$")
OWN_CLOSE = re.compile(u"^" + re.escape(END) + u"[ \\t]*$")
ANY_OPEN, ANY_CLOSE = u"# >>> FreeLab", u"# <<< FreeLab"
TITLE = u"Set Up FreeLab"
TOOLS = ("freelab_auto_kerning.py", "freelab_dark_mode.py", "freelab_tabs.py")  # the scripts the block loads

# The block, as tools/install-fontlab.ps1 holds it ($begin, $end, and the three paths filled in by block()).
BLOCK = u'''$begin (managed by FreeLab tools/install-fontlab.ps1; -Uninstall removes it)
def _freelab_tools_load(name, path):
    import os, sys
    if not os.path.isfile(path):
        return None
    os.environ["FREELAB_NO_AUTOSTART"] = "1"  # load only; this block decides what runs
    try:
        if sys.version_info[0] == 2:
            # open() takes a unicode path through the wide Windows API; imp.load_source does not.
            import imp
            module = imp.new_module(name)
            module.__file__ = path
            sys.modules[name] = module
            with open(path, "rb") as handle:
                source = handle.read()
            exec(compile(source, name + ".py", "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
    finally:
        del os.environ["FREELAB_NO_AUTOSTART"]
    sys.modules[name] = module
    return module
def _freelab_tools_startup():
    import sys
    try:
        # Scripts > FreeLab in working order, with separators (once FontLab has built the menu), each time:
        # Refresh Scripts builds the menu anew, and runs this script again (the module loaded already is
        # used: the hook does nothing on a menu it has hooked)
        tools = sys.modules.get("freelab_auto_kerning")
        if tools is None or not hasattr(tools, "hook_menu_order"):
            tools = _freelab_tools_load("freelab_auto_kerning", $kernPath)
        if tools is not None:
            getattr(tools, "hook_menu_order_soon", tools.hook_menu_order)()
    except Exception as exc:
        print("FreeLab menu at startup: %s" % (exc,))
    # The rest once a session: the startup script runs again as FontLab runs a script (live, November
    # 14: FreeLab MCP's block started its listener over each time a FreeLab tool opened), and dark
    # mode's startup (a full pass over every widget) and tab docking started over with it
    if getattr(sys, "_freelab_tools_started", False):
        return
    sys._freelab_tools_started = True
    try:
        module = _freelab_tools_load("freelab_dark_mode", $darkPath)
        if module is not None:
            module.startup()
    except Exception as exc:
        print("FreeLab dark mode at startup: %s" % (exc,))
    try:
        tabs = _freelab_tools_load("freelab_tabs", $tabsPath)
        if tabs is not None:
            tabs.startup()  # document tabs reorder and dock back as Photoshop's do (unless switched off)
    except Exception as exc:
        print("FreeLab tab docking at startup: %s" % (exc,))
try:
    _freelab_tools_startup()
except Exception:
    pass
$end'''


class Refused(Exception):
    """The startup script cannot be changed safely; the message says why, in words for the user."""


def py_literal(text):
    """A Python unicode literal that is pure ASCII (backslashes doubled, everything outside printable ASCII as
    \\uXXXX), so Python 2 reads it whatever the code page: the installer's ConvertTo-PyLiteral."""
    out = [u'u"']
    for ch in text:
        code = ord(ch)
        if ch == u"\\":
            out.append(u"\\\\")
        elif ch == u'"':
            out.append(u'\\"')
        elif code < 32 or code > 126:
            out.append(u"\\u%04x" % code)
        else:
            out.append(ch)
    out.append(u'"')
    return u"".join(out)


def block(folder):
    """FreeLab's block for the tools in folder (Scripts\\FreeLab), with Windows' separators as the installer
    writes them."""
    def path(name):
        return py_literal(folder.rstrip(u"\\/") + u"\\" + name)
    return (BLOCK.replace(u"$begin", BEGIN).replace(u"$end", END).replace(u"$kernPath", path(u"freelab_auto_kerning.py"))
            .replace(u"$darkPath", path(u"freelab_dark_mode.py")).replace(u"$tabsPath", path(u"freelab_tabs.py")))


def find_blocks(lines):
    """FreeLab's own blocks as (first line, last line) pairs, or None when the file's FreeLab markers do not
    pair: a block opened inside another, closed without being opened, never closed, or opened by one kind
    of marker and closed by another (FreeLab MCP's block's markers count). Markers are whole lines from the
    start of the line; marker text anywhere else is the user's."""
    found, start, mine = [], -1, False
    for i, line in enumerate(lines):
        if line.startswith(ANY_OPEN):
            if start >= 0:
                return None
            start, mine = i, bool(OWN_OPEN.match(line))
        elif line.startswith(ANY_CLOSE):
            if start < 0 or bool(OWN_CLOSE.match(line)) != mine:
                return None
            if mine:
                found.append((start, i))
            start = -1
    return None if start >= 0 else found


def remove_block(text):
    """The text without FreeLab's own blocks."""
    lines = text.split(u"\n")
    blocks = find_blocks(lines)
    if blocks is None:
        raise Refused(UNPAIRED)
    drop = set(i for first, last in blocks for i in range(first, last + 1))
    kept = [line for i, line in enumerate(lines) if i not in drop]
    return u"\n".join(kept).rstrip(u"\n") + u"\n"


def set_block(text, new_block):
    """The block put where it already is (another FreeLab block keeps its place), or appended."""
    lines = text.split(u"\n")
    blocks = find_blocks(lines)
    if blocks is None:
        raise Refused(UNPAIRED)
    if blocks:
        drop = set(i for first, last in blocks for i in range(first, last + 1))
        kept = []
        for i, line in enumerate(lines):
            if i == blocks[0][0]:
                kept.append(new_block)  # the first copy replaced, any later one taken out
            elif i not in drop:
                kept.append(line)
        return u"\n".join(kept)
    text = text.rstrip(u"\n")
    if text:
        text += u"\n"
    return text + new_block + u"\n"


UNPAIRED = (u"FontLab's startup script has a FreeLab begin marker without its end marker, or the reverse, so it is "
            u"left as it is. Remove the broken block by hand and run this again.")
NOT_UTF8 = u"FontLab's startup script is not UTF-8 text, so it is left as it is. Save it as UTF-8 and run this again."
NO_STARTUP = (u"FontLab has not made its startup script yet. Quit FontLab, start it again, and choose "
              u"<i>Scripts &gt; FreeLab &gt; Set Up FreeLab</i> once more.")


class Startup(object):
    """FontLab's startup script as read: its text with \\n line ends, and what to write it back with."""

    def __init__(self, path):
        self.path = path
        with io.open(path, "rb") as handle:
            data = handle.read()
        self.bom = data[:3] == b"\xef\xbb\xbf"
        try:
            original = (data[3:] if self.bom else data).decode("utf-8")
        except UnicodeDecodeError:
            raise Refused(NOT_UTF8)
        self.crlf = u"\r\n" in original
        self.text = original.replace(u"\r\n", u"\n")
        if find_blocks(self.text.split(u"\n")) is None:
            raise Refused(UNPAIRED)

    def changed(self, text):
        return text.rstrip(u"\n") != self.text.rstrip(u"\n")

    def save(self, text):
        """Written whole beside the file, then put in its place: the original kept once as .freelab-backup,
        the file each change replaces as .freelab-previous."""
        import shutil
        backup, previous, temp = self.path + ".freelab-backup", self.path + ".freelab-previous", self.path + ".freelab-new"
        if not os.path.isfile(backup):
            shutil.copyfile(self.path, backup)
        if self.crlf:
            text = text.replace(u"\n", u"\r\n")
        try:
            with io.open(temp, "wb") as handle:
                handle.write((b"\xef\xbb\xbf" if self.bom else b"") + text.encode("utf-8"))
            shutil.copyfile(self.path, previous)
            replace_file(temp, self.path)
        finally:
            if os.path.isfile(temp):
                os.remove(temp)
        self.text = text.replace(u"\r\n", u"\n")


def replace_file(source, target):
    """source moved over target in one step (Python 2 has no os.replace, and Windows' rename refuses a name
    that exists)."""
    if hasattr(os, "replace"):
        os.replace(source, target)
        return
    import ctypes
    if not ctypes.windll.kernel32.MoveFileExW(ctypes.c_wchar_p(source), ctypes.c_wchar_p(target), 1):  # REPLACE_EXISTING
        raise OSError("could not replace %s" % target)


def startup_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    if isinstance(base, bytes):
        base = base.decode(sys.getfilesystemencoding() or "mbcs")
    return os.path.join(base, u"FontLab", u"FontLab 7", u"startupScript.py")


def tools_folder():
    """The folder this script runs from (Scripts\\FreeLab), as text."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    if isinstance(here, bytes):
        here = here.decode(sys.getfilesystemencoding() or "mbcs")
    return here


def missing_tools(folder):
    return [name for name in TOOLS if not os.path.isfile(os.path.join(folder, name))]


def state(path=None, folder=None):
    """("absent" | "current" | "outdated", the startup script read), or Refused."""
    path, folder = path or startup_path(), folder or tools_folder()
    if not os.path.isfile(path):
        raise Refused(NO_STARTUP)
    startup = Startup(path)
    blocks = find_blocks(startup.text.split(u"\n"))
    if not blocks:
        return "absent", startup
    return ("outdated" if startup.changed(set_block(startup.text, block(folder))) else "current"), startup


def set_up(path=None, folder=None):
    """The block added or brought up to date: True when the startup script changed. Refused when the tools are
    not beside this script (the block would load nothing)."""
    folder = folder or tools_folder()
    missing = missing_tools(folder)
    if missing:
        raise Refused(u"%s is not in %s: unpack the whole FreeLab folder of the release into FontLab's Scripts "
                      u"folder, then run this again." % (u", ".join(missing), folder))
    _kind, startup = state(path, folder)
    text = set_block(startup.text, block(folder))
    if not startup.changed(text):
        return False
    startup.save(text)
    return True


def remove(path=None, folder=None):
    """The block taken out: True when the startup script changed."""
    _kind, startup = state(path, folder)
    text = remove_block(startup.text)
    if not startup.changed(text):
        return False
    startup.save(text)
    return True


def start_now(folder=None):
    """The block run at once, so the menu, tab docking, and dark mode start without a restart. Never raises."""
    try:
        exec(compile(block(folder or tools_folder()), "freelab_startup_block", "exec"), {"__name__": "freelab_startup_block"})
        return True
    except Exception as exc:
        print("FreeLab setup: the block could not be run now (%s); it runs at FontLab's next start." % (exc,))
        return False


def dark_mode_on():
    return bool((getattr(sys, "_freelab_dark_mode", None) or {}).get("on"))


SET_UP_DONE = (u"FreeLab is set up: <i>Scripts &gt; FreeLab</i> is in order, and tab docking and dark mode start with "
               u"FontLab from now on. The startup script as it was is kept beside it "
               u"(<i>startupScript.py.freelab-backup</i>).")
ASK_REMOVE = (u"FreeLab is set up already. Take it out of FontLab's startup script? The tools then stay in the "
              u"<i>Scripts</i> menu until you delete their folder, but nothing of FreeLab starts with FontLab.")
REMOVED = (u"FreeLab's block is out of FontLab's startup script. Restart FontLab, then delete the <i>FreeLab</i> "
           u"folder from its <i>Scripts</i> folder to remove the tools themselves.")
DARK_FIRST = (u"Dark mode is on. Switch it off first (<i>Scripts &gt; FreeLab &gt; Dark Mode</i>), so that FontLab "
              u"gets its own colors back, then run this again.")


def mcp_script_window(window):
    """Marks a message box as FreeLab's own (FreeLab MCP's convention: a script's dialog, never taken for a
    question of FontLab's). Returns it. Never raises."""
    try:
        window.setProperty("mcpScriptWindow", True)
    except Exception:
        pass
    return window


def _boxes():
    from PythonQt import QtGui
    parent = QtGui.QApplication.activeWindow()

    def tell(text):
        box = mcp_script_window(QtGui.QMessageBox(parent))
        box.setWindowTitle(TITLE)
        box.setText(text)
        box.exec_()

    def ask(text, yes, no):
        box = mcp_script_window(QtGui.QMessageBox(parent))
        box.setWindowTitle(TITLE)
        box.setText(text)
        accept = box.addButton(yes, QtGui.QMessageBox.AcceptRole)
        box.setDefaultButton(box.addButton(no, QtGui.QMessageBox.RejectRole))
        box.exec_()
        return box.clickedButton() == accept
    return tell, ask


def main(tell=None, ask=None, path=None, folder=None):
    """Set FreeLab up, or offer to take it out when it is set up already. What was done: "set up",
    "removed", "kept", or "refused"."""
    if tell is None or ask is None:
        tell, ask = _boxes()
    try:
        kind, _startup = state(path, folder)
        if kind == "current":
            if not ask(ASK_REMOVE, u"Remove", u"Keep"):
                return "kept"
            if dark_mode_on():
                tell(DARK_FIRST)
                return "refused"
            remove(path, folder)
            tell(REMOVED)
            return "removed"
        set_up(path, folder)
        start_now(folder)
        tell(SET_UP_DONE)
        return "set up"
    except Refused as refusal:
        tell(u"%s" % (refusal,))
        return "refused"
    except (IOError, OSError) as exc:
        tell(u"FontLab's startup script could not be written (%s). It is left as it was." % (exc,))
        return "refused"


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_setup":
    main()

"""Run every FreeLab test: listener and server under Python 3, then the listener under Python 2.7.

FontLab 7 embeds Python 2.7, so the Python 2.7 run is part of the gate. Get that
interpreter with tools/get-python27.ps1 (it lands in %LOCALAPPDATA%\\FreeLab, or
FREELAB_PY27_DIR). Python 2.7 opens files through the ANSI code page, so the
files it runs are copied to a temporary folder first.
The native pixel helper's tests need its DLL (tools/build-native.ps1).
Exit status is 1 when anything fails, and 2 when the 2.7 run could not happen
or tests were skipped (the native helper not built), unless --skip-py27 or
--skip-native allows it.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY27_DIR = Path(os.environ.get("FREELAB_PY27_DIR") or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FreeLab" / "python27")
PY27 = PY27_DIR / "tools" / "python.exe"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
PY27_FILES = (
    "listener/freelab_listener.py", "tests/fakes.py", "tests/listener_tests.py",
    "darkmode/freelab_dark_mode.py", "tests/qtfakes.py", "tests/darkmode_tests.py",
)
PY27_SUITES = ("tests/listener_tests.py", "tests/darkmode_tests.py")


def run_py3() -> tuple[bool, list[str]]:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="*_tests.py", top_level_dir=str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return result.wasSuccessful(), sorted(set(reason for _test, reason in result.skipped))


def run_py27() -> bool | None:
    if not PY27.is_file():
        return None
    env = dict(os.environ, PYTHONIOENCODING="utf-8", FREELAB_NO_AUTOSTART="1")
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    work = Path(tempfile.mkdtemp(prefix="freelab-py27-"))
    ok = True
    try:
        for rel in PY27_FILES:
            target = work / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)
        env["TEMP"] = env["TMP"] = str(work)
        for suite in PY27_SUITES:
            print("-- %s" % suite)
            proc = subprocess.run(
                # No -E: it would drop PYTHONIOENCODING; PYTHONPATH and PYTHONHOME are removed above instead.
                [str(PY27), "-s", "-B", str(work / suite)],
                cwd=str(work),
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=NO_WINDOW,
                timeout=300,
            )
            sys.stdout.write(proc.stdout)
            sys.stdout.write(proc.stderr)
            ok = ok and proc.returncode == 0
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-py27", action="store_true", help="do not fail when Python 2.7 is missing")
    parser.add_argument("--skip-native", action="store_true", help="do not fail when the native helper is not built")
    args = parser.parse_args()

    print("== Python %s: listener, dark mode, native helper, and server" % sys.version.split()[0])
    ok3, skipped = run_py3()
    for reason in skipped:
        print("SKIPPED: %s" % reason)

    print("\n== Python 2.7: listener and dark mode")
    ok27 = run_py27()
    if ok27 is None:
        print("Python 2.7 not found at %s; run tools/get-python27.ps1." % PY27)

    print("\nSUMMARY python3=%s python27=%s skipped=%d" % (
        "pass" if ok3 else "FAIL", {None: "missing", True: "pass", False: "FAIL"}[ok27], len(skipped)))
    if not ok3 or ok27 is False:
        return 1
    if ok27 is None and not args.skip_py27:
        return 2
    if skipped and not args.skip_native:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Run every FreeLab test: listener and server under Python 3, then the listener under Python 2.7.

FontLab 7 embeds Python 2.7, so the Python 2.7 run is part of the gate. Get that
interpreter with tools/get-python27.ps1 (it lands in %LOCALAPPDATA%\\FreeLab, or
FREELAB_PY27_DIR). Python 2.7 opens files through the ANSI code page, so the
files it runs are copied to a temporary folder first.
Exit status is nonzero when anything fails or the 2.7 run could not happen,
unless --skip-py27 is given.
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
PY27_FILES = ("listener/freelab_listener.py", "tests/fakes.py", "tests/listener_tests.py")


def run_py3() -> bool:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="*_tests.py", top_level_dir=str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return result.wasSuccessful()


def run_py27() -> bool | None:
    if not PY27.is_file():
        return None
    env = dict(os.environ, PYTHONIOENCODING="utf-8", FREELAB_NO_AUTOSTART="1")
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    work = Path(tempfile.mkdtemp(prefix="freelab-py27-"))
    try:
        for rel in PY27_FILES:
            target = work / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)
        env["TEMP"] = env["TMP"] = str(work)
        proc = subprocess.run(
            # No -E: it would drop PYTHONIOENCODING; PYTHONPATH and PYTHONHOME are removed above instead.
            [str(PY27), "-s", "-B", str(work / "tests" / "listener_tests.py")],
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
    finally:
        shutil.rmtree(work, ignore_errors=True)
    sys.stdout.write(proc.stdout)
    sys.stdout.write(proc.stderr)
    return proc.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-py27", action="store_true", help="do not fail when Python 2.7 is missing")
    args = parser.parse_args()

    print("== Python %s: listener and server" % sys.version.split()[0])
    ok3 = run_py3()

    print("\n== Python 2.7: listener")
    ok27 = run_py27()
    if ok27 is None:
        print("Python 2.7 not found at %s; run tools/get-python27.ps1." % PY27)

    print("\nSUMMARY python3=%s python27=%s" % ("pass" if ok3 else "FAIL", {None: "missing", True: "pass", False: "FAIL"}[ok27]))
    if not ok3 or ok27 is False:
        return 1
    if ok27 is None and not args.skip_py27:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

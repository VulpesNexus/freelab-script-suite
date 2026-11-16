"""Run every FreeLab test: dark mode and its native helper under Python 3, then dark mode under Python 2.7.

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
    "darkmode/freelab_dark_mode.py", "darkmode/freelab_dark_mode_settings.py", "tests/qtfakes.py",
    "tests/darkmode_tests.py", "kerning/freelab_auto_kerning.py", "kerning/freelab_kerning_check.py", "kerning/common_pairs.txt", "kerning/script_pairs.txt",
    "tests/kern_tests.py", "spacing/freelab_auto_spacing.py", "tests/spacing_tests.py",
    "compose/freelab_glyph_compose.py", "compose/glyph_names.json", "features/freelab_feature_code.py",
    "compose/freelab_glyph_generation.py", "compose/glyph_generation.json", "compose/glyph_generation_LICENSE",
    "tests/generation_tests.py",
    "tests/glyphtools_tests.py",
    "cjk/freelab_cjk_spacing.py", "tests/cjk_tests.py", "tests/features_tests.py",
    "cjk/freelab_cjk_vertical.py", "cjk/vertical_model.json", "tests/cjk_vertical_tests.py",
    "tools/add_vertical_metrics.py",
    "tests/glyphcodes_tests.py",
    "checks/freelab_font_check.py", "checks/language_coverage.json", "tests/fontcheck_tests.py",
    "checks/character_sets.json", "checks/character_sets_LICENSE", "checks/coverage_gaps.json",
    "checks/language_families.json", "checks/language_families_LICENSE", "checks/high_value_languages.json",
    "checks/language_orthographies.json", "checks/language_orthographies_LICENSE", "checks/font_characters.json",
    "checks/space_conventions.json",
    "compare/freelab_font_compare.py", "tests/compare_tests.py", "proof/freelab_proof.py", "tests/proof_tests.py",
    "windows/freelab_tabs.py", "tests/tabs_tests.py",
    "features/freelab_alternates.py", "features/alternates_model.json", "tests/alternates_tests.py",
    "checks/language_font/FreeLang-Essential.ttf", "checks/language_font/FreeLang-CJK.ttf",
    "checks/language_font/FreeLangPlus-General.ttf", "checks/language_font/FreeLangPlus-Mongolian-Tibetan.ttf",
    "checks/language_font/FreeLangPlus-Duployan.ttf", "checks/language_font/FreeLang_LICENSE",
    "checks/language_font/language_font.json", "tests/language_font_tests.py", "docs/COVERAGE-GAPS.md",
)
PY27_OPTIONAL = tuple("checks/language_font/%s" % name for name in (
    "FreeLang-CJK.ttf", "FreeLangPlus-General.ttf", "FreeLangPlus-Mongolian-Tibetan.ttf",
    "FreeLangPlus-Duployan.ttf"))
PY27_SUITES = ("tests/darkmode_tests.py", "tests/kern_tests.py", "tests/spacing_tests.py", "tests/glyphtools_tests.py",
               "tests/cjk_tests.py", "tests/cjk_vertical_tests.py", "tests/glyphcodes_tests.py",
               "tests/features_tests.py", "tests/fontcheck_tests.py",
               "tests/compare_tests.py", "tests/proof_tests.py", "tests/tabs_tests.py",
               "tests/alternates_tests.py", "tests/language_font_tests.py", "tests/generation_tests.py")


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
            if rel in PY27_OPTIONAL and not (ROOT / rel).is_file():
                continue  # (FreeLang's optional fonts, published beside a release: the tests skip what is absent)
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

    print("== Python %s: dark mode and native helper" % sys.version.split()[0])
    ok3, skipped = run_py3()
    for reason in skipped:
        print("SKIPPED: %s" % reason)

    print("\n== Python 2.7: dark mode")
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

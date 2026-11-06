# Python 2.7 for FontLab 7

FontLab 7 for Windows does not carry its own Python. Its *PythonQt.dll* links *python27.dll*, so scripting works only when a 64-bit Python 2.7 is installed where FontLab finds it; the FontLab 7 installer offers one, and FontLab's support pages recommend letting it install the bundled version. FontLab ships its own Python packages (fontTools and its documentation tools) in *Resources\python\2.7\site-packages* of its program folder.

Without that Python, FontLab still starts, but the *Scripting* panel, the *Scripts* menu, and the startup script do nothing, and so does the FreeLab listener.

## Check

1. Open *Window > Panels > Scripting*, type `import sys; print(sys.version)`, and run it.
2. It should print a 2.7 version. If nothing happens, Python is missing.

## Fix

Install the 64-bit Python 2.7.18 (*python-2.7.18.amd64.msi* from python.org), or rerun the FontLab 7 installer and let it install Python. Then restart FontLab and check again.

The 32-bit installer (*python-2.7.18.msi*, the one python.org lists first) does not work: it puts *python27.dll* in *SysWOW64*, where 64-bit FontLab cannot load it, and FontLab shows no error. The 64-bit one puts it in *System32*. Leave out *Register Extensions* when installing, or Python 2.7 takes over double-clicked *.py* files.

## Paths

Python 2.7 opens files through the Windows ANSI code page. A script whose path that code page cannot spell, such as a folder with an en dash on a Japanese-locale system, cannot be run, so keep the listener in FontLab's own *Scripts* folder.

## The test interpreter

*tools/get-python27.ps1* is separate: it fetches the official Python 2.7.18 NuGet package into *%LOCALAPPDATA%\FreeLab\python27* so the test gate can run the listener under the real 2.7. It installs nothing, and FontLab does not use it.

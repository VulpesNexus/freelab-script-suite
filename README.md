# FreeLab

Tools for FontLab, gathered in one place: an MCP server that lets an AI app such as Claude Code read the font open in FontLab 7, and a dark mode for FontLab 7's interface.

**Status: 0.2.0.** Dark mode runs in FontLab 7.2. The listener runs there too, and `fontlab_status` and `run_python` drove the whole dark-mode work, but the font reads are not proven live yet: [docs/FONTLAB7-API.md](docs/FONTLAB7-API.md) tracks each call.

## What is here

- *listener/freelab_listener.py*: a script you run inside FontLab. It answers requests on `127.0.0.1` only, from FontLab's main thread.
- *darkmode/*: *Scripts > FreeLab: Toggle Dark Mode* turns FontLab 7 dark (panels, tool bar, rulers, canvas, icons, and title bar) and back, without a restart, and remembers the choice for the next launch. *Scripts > FreeLab: Dark Mode Settings* offers a dark interface with FontLab's light canvas, and following Windows' light or dark mode. How it works, and what it costs: [docs/DARKMODE.md](docs/DARKMODE.md).
- *server/*: the MCP server your AI app starts. It never touches FontLab directly; it passes each tool call to the listener.
- *tests/*: the test gate (*run_tests.py*).
- *tools/*: helper scripts.

## Requirements

- FontLab 7 for Windows (developed against 7.2.0), with its Python working. FontLab 7 runs scripts with a **64-bit** Python 2.7 installed on the system (a 32-bit one does not work); the FontLab 7 installer offers one. If *Window > Panels > Scripting* cannot run a one-line `print(1)`, fix that first: [docs/PYTHON27.md](docs/PYTHON27.md).
- For dark mode, LLVM (clang) or Visual Studio with the C++ tools, to build its small native helper once. Without it, dark mode still works, with flipped hues in the widgets FontLab paints itself.
- Python 3.10 or newer with the `mcp` package (`pip install mcp`), for the server.

## Install

1. With FontLab closed, run *tools/install-fontlab.ps1*. It copies the listener and the dark-mode script into FontLab's user *Scripts* folder (*Documents\FontLab\FontLab 7\Scripts*), adds a marked block to FontLab's startup script that applies dark mode at launch when it was left on, and builds dark mode's native helper into *%LOCALAPPDATA%\FreeLab\bin*; the original startup script is kept as *startupScript.py.freelab-backup*, and `-Uninstall` takes it all out again. Scripts run from that folder, not from this repository: Python 2.7 cannot open files whose path the Windows ANSI code page cannot spell.
2. Register the server with your MCP client. For Claude Code:

   ```
   claude mcp add freelab -- python <path to this repository>\server\run_server.py
   ```

## Use

1. In FontLab, choose *Scripts > FreeLab: Start Listener* (or open the file in the *Scripting* panel and run it). The *Output* panel shows the listener's version and port. Run it again to restart it; start it again after every FontLab launch, or install with `-ListenerAtLaunch` to have FontLab start it at every launch.
2. Ask the AI app, for example, "check the FontLab connection" or "describe the glyph A".

Tools: `fontlab_status`, `get_current_font`, `list_glyphs`, `get_glyph`, `get_glyph_outline`, and `run_python`, which runs code inside FontLab for probing. `launch_fontlab`, `quit_fontlab`, and `restart_fontlab` start and close FontLab when you ask; quitting is refused while any font or the workspace has unsaved changes.

## What it does not do

- It does not write to fonts through dedicated tools yet; only `run_python` can, and only when asked to.
- It never saves, exports, or closes a font.
- It reads the font in front only, and outline coordinates are shape-local: each shape's transform is reported, not applied.
- FontLab 8 is untested. The listener is written to run there too.

## Tests

```
python tests/run_tests.py
```

It runs everything under Python 3, including the native helper's tests, then the listener and dark-mode tests under Python 2.7, which *tools/get-python27.ps1* fetches (a hash-checked copy of the official package, kept outside the repository). The gate fails if the Python 2.7 run is missing or the native helper is not built (*tools/build-native.ps1*).

## More

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): processes, protocol, discovery, and error model.
- [docs/DARKMODE.md](docs/DARKMODE.md): how FontLab 7 colors itself, and how dark mode turns each part dark.
- [docs/FONTLAB7-API.md](docs/FONTLAB7-API.md): the FontLab calls in use and how far each is proven.
- [docs/PRIOR-ART.md](docs/PRIOR-ART.md): the existing FontLab MCP servers, and why FreeLab does not build on them.
- [docs/ROADMAP.md](docs/ROADMAP.md): what comes next.
- [docs/FEATURE-SURVEY.md](docs/FEATURE-SURVEY.md): what already exists for dark mode, kerning, diacritics, and feature code.

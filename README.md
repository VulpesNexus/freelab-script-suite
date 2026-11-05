# FreeLab

Tools for FontLab, gathered in one place: an MCP server that lets an AI app such as Claude Code read the font open in FontLab 7, and a dark mode for FontLab 7's interface.

**Status: 0.1.0, groundwork.** Every part passes its tests against fakes, under Python 3 and under Python 2.7, but none of it has run inside FontLab yet: FontLab 7's Python is not working on the development machine (see *Requirements*). Which FontLab calls are proven is tracked in [docs/FONTLAB7-API.md](docs/FONTLAB7-API.md).

## What is here

- *listener/freelab_listener.py*: a script you run inside FontLab. It answers requests on `127.0.0.1` only, from FontLab's main thread.
- *darkmode/freelab_dark_mode.py*: *Scripts > FreeLab: Toggle Dark Mode* switches FontLab's menus, panels, and dialogs to a dark palette and back, without a restart, and remembers the choice for the next launch. The glyph canvas and font window keep the colors set in FontLab's *Preferences*.
- *server/*: the MCP server your AI app starts. It never touches FontLab directly; it passes each tool call to the listener.
- *tests/*: the test gate (*run_tests.py*).
- *tools/*: helper scripts.

## Requirements

- FontLab 7 for Windows (developed against 7.2.0), with its Python working. FontLab 7 runs scripts with a 64-bit Python 2.7 installed on the system; the FontLab 7 installer offers one. If *Window > Panels > Scripting* cannot run a one-line `print(1)`, fix that first: [docs/PYTHON27.md](docs/PYTHON27.md).
- Python 3.10 or newer with the `mcp` package (`pip install mcp`), for the server.

## Install

1. With FontLab closed, run *tools/install-fontlab.ps1*. It copies the listener and the dark-mode script into FontLab's user *Scripts* folder (*Documents\FontLab\FontLab 7\Scripts*), and adds a marked block to FontLab's startup script that applies dark mode at launch when it was left on; the original startup script is kept as *startupScript.py.freelab-backup*, and `-Uninstall` takes it all out again. Scripts run from that folder, not from this repository: Python 2.7 cannot open files whose path the Windows ANSI code page cannot spell.
2. Register the server with your MCP client. For Claude Code:

   ```
   claude mcp add freelab -- python <path to this repository>\server\run_server.py
   ```

## Use

1. In FontLab, choose *Scripts > FreeLab: Start Listener* (or open the file in the *Scripting* panel and run it). The *Output* panel shows the listener's version and port. Run it again to restart it; start it again after every FontLab launch.
2. Ask the AI app, for example, "check the FontLab connection" or "describe the glyph A".

Tools: `fontlab_status`, `get_current_font`, `list_glyphs`, `get_glyph`, `get_glyph_outline`, and `run_python`, which runs code inside FontLab for probing.

## What it does not do

- It does not write to fonts through dedicated tools yet; only `run_python` can, and only when asked to.
- It never saves, exports, or closes a font.
- It reads the font in front only, and outline coordinates are shape-local: each shape's transform is reported, not applied.
- FontLab 8 is untested. The listener is written to run there too.

## Tests

```
python tests/run_tests.py
```

It runs everything under Python 3, then the listener tests under Python 2.7, which *tools/get-python27.ps1* fetches (a hash-checked copy of the official package, kept outside the repository). The gate fails if the Python 2.7 run is missing.

## More

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): processes, protocol, discovery, and error model.
- [docs/FONTLAB7-API.md](docs/FONTLAB7-API.md): the FontLab calls in use and how far each is proven.
- [docs/PRIOR-ART.md](docs/PRIOR-ART.md): the existing FontLab MCP servers, and why FreeLab does not build on them.
- [docs/ROADMAP.md](docs/ROADMAP.md): what comes next.
- [docs/FEATURE-SURVEY.md](docs/FEATURE-SURVEY.md): what already exists for dark mode, kerning, diacritics, and feature code.

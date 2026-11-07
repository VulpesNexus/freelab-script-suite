# Install FreeLab's FontLab 7 scripts for the current user, or remove them.
#
#   install-fontlab.ps1             copy the listener and the dark-mode scripts into
#                                   FontLab 7's Scripts\FreeLab folder (a FreeLab
#                                   submenu of the Scripts menu), and add the FreeLab
#                                   block to FontLab's startupScript.py
#   install-fontlab.ps1 -Uninstall  remove that block, the two copied scripts, the
#                                   native helper, and dark mode's settings, putting
#                                   back the workspace color dark mode replaced
#
# Install also builds dark mode's native pixel helper (tools/build-native.ps1)
# into %LOCALAPPDATA%\FreeLab\bin when it is missing; without a compiler, dark
# mode still works, with plain inversion in the widgets FontLab paints itself.
# The first install keeps the original startup script as
# startupScript.py.freelab-backup. Quit FontLab first or restart it afterwards:
# FontLab reads its Scripts folder and startup script when it starts.
#
# ASCII only: Windows PowerShell 5.1 reads a BOM-less script in the ANSI code page.

# -ScriptsDir, -StartupScript, -BinDir, -StateDir, -RegistryKey, and -ProcessName override the
# locations and the FontLab process name, for testing.
# -ListenerAtLaunch also starts the MCP listener at every FontLab launch, so an AI app can
# reach FontLab (and its launch_fontlab tool can start it) without a click in FontLab.
param([switch]$Uninstall, [switch]$ListenerAtLaunch, [string]$ScriptsDir, [string]$StartupScript, [string]$BinDir,
      [string]$StateDir, [string]$RegistryKey, [string]$ProcessName = 'FontLab 7')

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$utf8 = New-Object System.Text.UTF8Encoding $false

if ($ScriptsDir) { $scripts = $ScriptsDir }
else {
    # FontLab 7's own data folder setting, else its default under Documents.
    $dataPath = $null
    try { $dataPath = (Get-ItemProperty 'HKCU:\Software\Fontlab\fontlab7' -Name 'general.data_path' -ErrorAction Stop).'general.data_path' } catch { }
    if (-not $dataPath) { $dataPath = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'FontLab\FontLab 7' }
    $scripts = Join-Path ($dataPath -replace '/', '\') 'Scripts'
}
$rootScripts = $scripts
$scripts = Join-Path $rootScripts 'FreeLab'  # its own submenu of the Scripts menu
if ($StartupScript) { $startup = $StartupScript }
else { $startup = Join-Path $env:LOCALAPPDATA 'FontLab\FontLab 7\startupScript.py' }
$files = @(
    @{ From = 'listener\freelab_listener.py'; Name = 'freelab_listener.py' },
    @{ From = 'darkmode\freelab_dark_mode.py'; Name = 'freelab_dark_mode.py' },
    @{ From = 'darkmode\freelab_dark_mode_settings.py'; Name = 'freelab_dark_mode_settings.py' }
)
if (-not $BinDir) { $BinDir = Join-Path $env:LOCALAPPDATA 'FreeLab\bin' }
if (-not $StateDir) { $StateDir = Join-Path $env:LOCALAPPDATA 'FreeLab' }
if (-not $RegistryKey) { $RegistryKey = 'HKCU:\Software\Fontlab\fontlab7' }
$darkWorkspace = '#fff0f0f0'  # WORKSPACE_DARK in darkmode/freelab_dark_mode.py
$source = [System.IO.File]::ReadAllText((Join-Path $repo 'darkmode\native\freelab_pixels.c'))
$nativeName = 'freelab_pixels-v' + [regex]::Match($source, '#define FREELAB_PIXELS_VERSION (\d+)').Groups[1].Value + '.dll'
$begin = '# >>> FreeLab'
$end = '# <<< FreeLab'

function Remove-Block([string]$text) {
    $pattern = '(?s)\n?' + [regex]::Escape($begin) + '.*?' + [regex]::Escape($end) + '[^\n]*\n?'
    return [regex]::Replace($text, $pattern, "`n").TrimEnd("`n") + "`n"
}

# A Python string literal that is pure ASCII: backslashes doubled, everything
# outside ASCII as \uXXXX, so Python 2 reads it whatever the code page.
function ConvertTo-PyLiteral([string]$s) {
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('u"')
    foreach ($ch in $s.ToCharArray()) {
        $code = [int]$ch
        if ($ch -eq '\') { [void]$sb.Append('\\') }
        elseif ($ch -eq '"') { [void]$sb.Append('\"') }
        elseif ($code -lt 32 -or $code -gt 126) { [void]$sb.Append(('\u{0:x4}' -f $code)) }
        else { [void]$sb.Append($ch) }
    }
    [void]$sb.Append('"')
    return $sb.ToString()
}

$current = ''
if (Test-Path $startup) { $current = [System.IO.File]::ReadAllText($startup) -replace "`r`n", "`n" }

if ($Uninstall) {
    # Dark mode keeps FontLab's own workspace color in darkmode.json while it is on.
    $settingsFile = Join-Path $StateDir 'darkmode.json'
    if (Test-Path $settingsFile) {
        $saved = $null
        try { $saved = ([System.IO.File]::ReadAllText($settingsFile) | ConvertFrom-Json).saved_workspace } catch { }
        if ($saved -and (Get-Process -Name $ProcessName -ErrorAction SilentlyContinue)) {
            Write-Output 'FontLab is running with dark mode on: switch dark mode off (Scripts > FreeLab > Toggle Dark Mode), quit FontLab, and run -Uninstall again.'
            exit 1
        }
        if ($saved) {
            $current = $null
            try { $current = (Get-ItemProperty $RegistryKey -Name 'color.workspace' -ErrorAction Stop).'color.workspace' } catch { }
            if ($current -eq $darkWorkspace) {
                Set-ItemProperty $RegistryKey -Name 'color.workspace' -Value $saved
                Write-Output "Put FontLab's workspace color back to $saved"
            }
        }
        [System.IO.File]::Delete($settingsFile)
        Write-Output "Removed $settingsFile"
    }
    if (Test-Path $startup) {
        [System.IO.File]::WriteAllText($startup, (Remove-Block $current), $utf8)
        Write-Output "Removed the FreeLab block from $startup"
    }
    foreach ($f in $files) {
        foreach ($dir in @($scripts, $rootScripts)) {  # the Scripts folder itself held them before 0.3
            $target = Join-Path $dir $f.Name
            if (Test-Path $target) { [System.IO.File]::Delete($target); Write-Output "Removed $target" }
        }
    }
    if ((Test-Path $scripts) -and -not (Get-ChildItem $scripts -Force)) {
        [System.IO.Directory]::Delete($scripts); Write-Output "Removed $scripts"
    }
    if (Test-Path $BinDir) {
        foreach ($dll in Get-ChildItem $BinDir -Filter 'freelab_pixels*.dll') {
            try { [System.IO.File]::Delete($dll.FullName); Write-Output "Removed $($dll.FullName)" }
            catch { Write-Output "Could not remove $($dll.FullName) (FontLab is using it): delete it after quitting FontLab." }
        }
    }
    exit 0
}

if (-not (Test-Path $scripts)) { New-Item -ItemType Directory -Path $scripts | Out-Null }
foreach ($f in $files) {
    $target = Join-Path $scripts $f.Name
    [System.IO.File]::Copy((Join-Path $repo $f.From), $target, $true)
    Write-Output "Copied $($f.Name) to $scripts"
    $old = Join-Path $rootScripts $f.Name  # before 0.3 they sat in the Scripts folder itself
    if (Test-Path $old) { [System.IO.File]::Delete($old); Write-Output "Removed the old $old" }
}

$native = Join-Path $BinDir $nativeName
if (Test-Path $native) { Write-Output "Native helper present: $native" }
else {
    try { & (Join-Path $PSScriptRoot 'build-native.ps1') -Out $native }
    catch {
        Write-Output "Could not build the native helper: $_"
        Write-Output 'Dark mode still works, with plain inversion in the widgets FontLab paints itself. Install LLVM or Visual Studio with the C++ tools, then run tools\build-native.ps1.'
    }
}

$darkPath = ConvertTo-PyLiteral (Join-Path $scripts 'freelab_dark_mode.py')
$listenerPath = ConvertTo-PyLiteral (Join-Path $scripts 'freelab_listener.py')
$startListener = if ($ListenerAtLaunch) { 'True' } else { 'False' }
$block = @"
$begin (managed by FreeLab tools/install-fontlab.ps1; -Uninstall removes it)
def _freelab_load(name, path):
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
def _freelab_startup():
    try:
        module = _freelab_load("freelab_dark_mode", $darkPath)
        if module is not None:
            module.startup()
    except Exception as exc:
        print("FreeLab dark mode at startup: %s" % (exc,))
    if ${startListener}:
        try:
            module = _freelab_load("freelab_listener", $listenerPath)
            if module is not None:
                module.main()
        except Exception as exc:
            print("FreeLab listener at startup: %s" % (exc,))
try:
    _freelab_startup()
except Exception:
    pass
$end
"@ -replace "`r`n", "`n"

if ((Test-Path $startup) -and -not (Test-Path "$startup.freelab-backup")) {
    [System.IO.File]::Copy($startup, "$startup.freelab-backup")
    Write-Output "Kept the original startup script as $startup.freelab-backup"
}
$folder = Split-Path -Parent $startup
if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Path $folder | Out-Null }
$text = (Remove-Block $current).TrimEnd("`n")
if ($text) { $text += "`n" }
[System.IO.File]::WriteAllText($startup, $text + $block + "`n", $utf8)
Write-Output "Added the FreeLab block to $startup"

# Install FreeLab's FontLab 7 scripts for the current user, or remove them.
#
#   install-fontlab.ps1             copy the listener and the dark-mode script into
#                                   FontLab 7's Scripts folder, and add the FreeLab
#                                   block to FontLab's startupScript.py
#   install-fontlab.ps1 -Uninstall  remove that block and the two copied scripts
#
# The first install keeps the original startup script as
# startupScript.py.freelab-backup. Quit FontLab first or restart it afterwards:
# FontLab reads its Scripts folder and startup script when it starts.
#
# ASCII only: Windows PowerShell 5.1 reads a BOM-less script in the ANSI code page.

# -ScriptsDir and -StartupScript override the two locations, for testing.
param([switch]$Uninstall, [string]$ScriptsDir, [string]$StartupScript)

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
if ($StartupScript) { $startup = $StartupScript }
else { $startup = Join-Path $env:LOCALAPPDATA 'FontLab\FontLab 7\startupScript.py' }
$files = @(
    @{ From = 'listener\freelab_listener.py'; Name = 'freelab_listener.py' },
    @{ From = 'darkmode\freelab_dark_mode.py'; Name = 'freelab_dark_mode.py' }
)
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
    if (Test-Path $startup) {
        [System.IO.File]::WriteAllText($startup, (Remove-Block $current), $utf8)
        Write-Output "Removed the FreeLab block from $startup"
    }
    foreach ($f in $files) {
        $target = Join-Path $scripts $f.Name
        if (Test-Path $target) { [System.IO.File]::Delete($target); Write-Output "Removed $target" }
    }
    exit 0
}

if (-not (Test-Path $scripts)) { New-Item -ItemType Directory -Path $scripts | Out-Null }
foreach ($f in $files) {
    $target = Join-Path $scripts $f.Name
    [System.IO.File]::Copy((Join-Path $repo $f.From), $target, $true)
    Write-Output "Copied $($f.Name) to $scripts"
}

$darkPath = ConvertTo-PyLiteral (Join-Path $scripts 'freelab_dark_mode.py')
$block = @"
$begin (managed by FreeLab tools/install-fontlab.ps1; -Uninstall removes it)
def _freelab_startup():
    import os, sys
    path = $darkPath
    if not os.path.isfile(path):
        return
    try:
        if sys.version_info[0] == 2:
            # open() takes a unicode path through the wide Windows API; imp.load_source does not.
            import imp
            module = imp.new_module("freelab_dark_mode")
            module.__file__ = path
            sys.modules["freelab_dark_mode"] = module
            with open(path, "rb") as handle:
                source = handle.read()
            exec(compile(source, "freelab_dark_mode.py", "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location("freelab_dark_mode", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["freelab_dark_mode"] = module
            spec.loader.exec_module(module)
        sys.modules["freelab_dark_mode"] = module
        module.startup()
    except Exception as exc:
        print("FreeLab startup: %s" % (exc,))
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

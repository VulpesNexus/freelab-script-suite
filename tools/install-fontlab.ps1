# Install FreeLab's FontLab 7 tools (dark mode) for the current user, or remove them.
#
#   install-fontlab.ps1             copy the dark-mode scripts into FontLab 7's
#                                   Scripts\FreeLab folder (a FreeLab submenu of the
#                                   Scripts menu), and add the FreeLab tools block to
#                                   FontLab's startupScript.py
#   install-fontlab.ps1 -Uninstall  remove that block, the copied scripts, the native
#                                   helper, and dark mode's settings, putting back the
#                                   workspace color dark mode replaced
#
# FreeLab MCP, a separate repository, installs its listener beside these with a
# startup block of its own: either can be installed or removed without the other.
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
param([switch]$Uninstall, [string]$ScriptsDir, [string]$StartupScript, [string]$BinDir,
      [string]$StateDir, [string]$RegistryKey, [string]$ProcessName = 'FontLab 7')

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

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
    @{ From = 'darkmode\freelab_dark_mode.py'; Name = 'freelab_dark_mode.py' },
    @{ From = 'darkmode\freelab_dark_mode_settings.py'; Name = 'freelab_dark_mode_settings.py' }
)
if (-not $BinDir) { $BinDir = Join-Path $env:LOCALAPPDATA 'FreeLab\bin' }
if (-not $StateDir) { $StateDir = Join-Path $env:LOCALAPPDATA 'FreeLab' }
if (-not $RegistryKey) { $RegistryKey = 'HKCU:\Software\Fontlab\fontlab7' }
$darkWorkspace = '#fff0f0f0'  # WORKSPACE_DARK in darkmode/freelab_dark_mode.py
$source = [System.IO.File]::ReadAllText((Join-Path $repo 'darkmode\native\freelab_pixels.c'))
$nativeName = 'freelab_pixels-v' + [regex]::Match($source, '#define FREELAB_PIXELS_VERSION (\d+)').Groups[1].Value + '.dll'
$begin = '# >>> FreeLab tools'
$end = '# <<< FreeLab tools'

function Remove-Block([string]$text) {
    $pattern = '(?s)\n?' + [regex]::Escape($begin) + '.*?' + [regex]::Escape($end) + '[^\n]*\n?'
    return [regex]::Replace($text, $pattern, "`n").TrimEnd("`n") + "`n"
}

# The one block FreeLab wrote before the MCP and the tools became separate repositories
# (dark mode and the listener together). Either installer takes it out and says so.
$legacyPattern = '(?s)\n?# >>> FreeLab \(managed.*?# <<< FreeLab[ \t]*(\n|$)'

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

# FontLab's startup script is read as strict UTF-8 (a BOM is kept) and written back with its own
# line endings, and only when it changes. A file that is not UTF-8, or whose FreeLab markers are
# not paired, is left alone: rewriting it would replace characters or delete the user's code.
$current = ''
$normalized = ''
$bom = $false
$crlf = $false
if (Test-Path $startup) {
    $bytes = [System.IO.File]::ReadAllBytes($startup)
    $bom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
    $skip = 0
    if ($bom) { $skip = 3 }
    $strict = New-Object System.Text.UTF8Encoding $false, $true
    try { $original = $strict.GetString($bytes, $skip, $bytes.Length - $skip) }
    catch {
        Write-Output "$startup is not UTF-8 text, so it is left as it is. Save it as UTF-8 and run this again."
        exit 1
    }
    $crlf = $original.Contains("`r`n")
    $normalized = $original -replace "`r`n", "`n"
    $current = $normalized
}
function Test-Paired([string]$text, [string]$open, [string]$close) {
    return ([regex]::Matches($text, '(?m)^' + $open)).Count -eq ([regex]::Matches($text, '(?m)^' + $close + '[ \t]*$')).Count
}
if (-not (Test-Paired $current ([regex]::Escape($begin)) ([regex]::Escape($end))) -or
    -not (Test-Paired $current '# >>> FreeLab \(managed' '# <<< FreeLab')) {
    Write-Output "$startup has a FreeLab begin marker without its end marker, or the reverse, so it is left as it is. Remove the broken block by hand and run this again."
    exit 1
}
function Test-Changed([string]$text) {
    return $text.TrimEnd("`n") -ne $normalized.TrimEnd("`n")
}
function Save-Startup([string]$text) {
    if ((Test-Path $startup) -and -not (Test-Path "$startup.freelab-backup")) {
        [System.IO.File]::Copy($startup, "$startup.freelab-backup")
        Write-Host "Kept the original startup script as $startup.freelab-backup"
    }
    $folder = Split-Path -Parent $startup
    if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Path $folder | Out-Null }
    if ($crlf) { $text = $text -replace "`n", "`r`n" }
    [System.IO.File]::WriteAllText($startup, $text, (New-Object System.Text.UTF8Encoding $bom))
}
$legacy = [regex]::IsMatch($current, $legacyPattern)
if ($legacy) { $current = [regex]::Replace($current, $legacyPattern, "`n").TrimEnd("`n") + "`n" }
function Write-LegacyNote {
    if ($legacy) {
        Write-Output 'Removed the combined FreeLab block of earlier versions, which also started the MCP listener. To keep that, run tools\install-fontlab.ps1 -ListenerAtLaunch from FreeLab MCP.'
    }
}

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
            $workspace = $null
            try { $workspace = (Get-ItemProperty $RegistryKey -Name 'color.workspace' -ErrorAction Stop).'color.workspace' } catch { }
            if ($workspace -eq $darkWorkspace) {
                Set-ItemProperty $RegistryKey -Name 'color.workspace' -Value $saved
                Write-Output "Put FontLab's workspace color back to $saved"
            }
        }
        [System.IO.File]::Delete($settingsFile)
        Write-Output "Removed $settingsFile"
    }
    if (Test-Path $startup) {
        $text = Remove-Block $current
        if (Test-Changed $text) {
            Save-Startup $text
            Write-Output "Removed the FreeLab tools block from $startup"
            Write-LegacyNote
        }
    }
    # The stylesheet images dark mode mapped, and its log.
    $cache = Join-Path $StateDir 'cache'
    if (Test-Path $cache) {
        foreach ($dir in Get-ChildItem $cache -Directory -Filter 'images-*') {
            [System.IO.Directory]::Delete($dir.FullName, $true); Write-Output "Removed $($dir.FullName)"
        }
        if (-not (Get-ChildItem $cache -Force)) { [System.IO.Directory]::Delete($cache) }
    }
    $log = Join-Path $StateDir 'darkmode.log'
    if (Test-Path $log) { [System.IO.File]::Delete($log); Write-Output "Removed $log" }
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
if ((Test-Path $native) -and (Test-Path $BinDir)) {
    # Earlier versions: FontLab keeps the one it loaded locked until it quits, so a locked one waits for the next install.
    foreach ($dll in Get-ChildItem $BinDir -Filter 'freelab_pixels*.dll') {
        if ($dll.Name -eq $nativeName) { continue }
        try { [System.IO.File]::Delete($dll.FullName); Write-Output "Removed the superseded $($dll.FullName)" } catch { }
    }
}

$darkPath = ConvertTo-PyLiteral (Join-Path $scripts 'freelab_dark_mode.py')
$block = @"
$begin (managed by FreeLab tools/install-fontlab.ps1; -Uninstall removes it)
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
    try:
        module = _freelab_tools_load("freelab_dark_mode", $darkPath)
        if module is not None:
            module.startup()
    except Exception as exc:
        print("FreeLab dark mode at startup: %s" % (exc,))
try:
    _freelab_tools_startup()
except Exception:
    pass
$end
"@ -replace "`r`n", "`n"

$text = (Remove-Block $current).TrimEnd("`n")
if ($text) { $text += "`n" }
$text += $block + "`n"
if (Test-Changed $text) {
    Save-Startup $text
    Write-Output "Added the FreeLab tools block to $startup"
    Write-LegacyNote
}
else { Write-Output "The FreeLab tools block in $startup is up to date" }

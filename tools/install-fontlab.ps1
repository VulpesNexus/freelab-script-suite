# Install FreeLab's FontLab 7 tools (dark mode, auto kerning) for the current user, or remove them.
#
#   install-fontlab.ps1             copy the dark-mode and auto kerning scripts into FontLab 7's
#                                   Scripts\FreeLab folder (a FreeLab submenu of the
#                                   Scripts menu), and add the FreeLab tools block to
#                                   FontLab's startupScript.py
#   install-fontlab.ps1 -Uninstall  remove that block, the copied scripts, the native
#                                   helper, dark mode's settings (putting back the
#                                   workspace color dark mode replaced), the tools'
#                                   window size, and Proof's settings
#
# FreeLab MCP, a separate repository, installs its listener beside these with a
# startup block of its own: either can be installed or removed without the other.
#
# Install also builds dark mode's native pixel helper, its native engine, and the auto kerning
# core (tools/build-native.ps1)
# into %LOCALAPPDATA%\FreeLab\bin when it is missing; without a compiler, dark
# mode still works, with plain inversion in the widgets FontLab paints itself; the
# auto kerning core is required (the exit status is 1 without it).
# The first install keeps the original startup script as
# startupScript.py.freelab-backup, and each change keeps the file it replaced as
# startupScript.py.freelab-previous. Quit FontLab first or restart it afterwards:
# FontLab reads its Scripts folder and startup script when it starts.
# The exit status is 1 when anything required could not be done (listed at the
# end); a font FontLab holds open is replaced at the next install.
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
    @{ From = 'darkmode\freelab_dark_mode_settings.py'; Name = 'freelab_dark_mode_settings.py' },
    @{ From = 'windows\freelab_tabs.py'; Name = 'freelab_tabs.py' },
    @{ From = 'kerning\freelab_auto_kerning.py'; Name = 'freelab_auto_kerning.py' },
    @{ From = 'kerning\freelab_kerning_check.py'; Name = 'freelab_kerning_check.py' },
    @{ From = 'checks\freelab_font_check.py'; Name = 'freelab_font_check.py' },
    @{ From = 'compare\freelab_font_compare.py'; Name = 'freelab_font_compare.py' },
    # Family Audit reads layers and splits features with Font Compare's code (loaded beside it)
    @{ From = 'checks\freelab_family_audit.py'; Name = 'freelab_family_audit.py' },
    # The font info kept in step with the tools' writes: a helper module, no menu entry of its own
    @{ From = 'checks\freelab_font_info.py'; Name = 'freelab_font_info.module' },
    @{ From = 'proof\freelab_proof.py'; Name = 'freelab_proof.py' },
    @{ From = 'checks\language_coverage.json'; Name = 'language_coverage.json' },
    @{ From = 'checks\language_coverage_LICENSE'; Name = 'language_coverage_LICENSE' },
    @{ From = 'checks\character_sets.json'; Name = 'character_sets.json' },
    @{ From = 'checks\character_sets_LICENSE'; Name = 'character_sets_LICENSE' },
    @{ From = 'checks\coverage_gaps.json'; Name = 'coverage_gaps.json' },
    @{ From = 'checks\language_families.json'; Name = 'language_families.json' },
    @{ From = 'checks\language_families_LICENSE'; Name = 'language_families_LICENSE' },
    @{ From = 'checks\language_orthographies.json'; Name = 'language_orthographies.json' },
    @{ From = 'checks\language_orthographies_LICENSE'; Name = 'language_orthographies_LICENSE' },
    @{ From = 'checks\space_conventions.json'; Name = 'space_conventions.json' },
    @{ From = 'checks\high_value_languages.json'; Name = 'high_value_languages.json' },
    @{ From = 'checks\language_font\FreeLang-Essential.ttf'; Name = 'FreeLang-Essential.ttf' },
    # Optional: the repository holds the Essential font alone, and each release publishes these four
    # beside it (FreeLang-Extras.zip, unpacked into checks\language_font). Font Check works without
    # them (their scripts are then left to the system's fonts), so a copy without them still installs.
    @{ From = 'checks\language_font\FreeLang-CJK.ttf'; Name = 'FreeLang-CJK.ttf'; Optional = $true },
    @{ From = 'checks\language_font\FreeLangPlus-General.ttf'; Name = 'FreeLangPlus-General.ttf'; Optional = $true },
    @{ From = 'checks\language_font\FreeLangPlus-Mongolian-Tibetan.ttf'; Name = 'FreeLangPlus-Mongolian-Tibetan.ttf'; Optional = $true },
    @{ From = 'checks\language_font\FreeLangPlus-Duployan.ttf'; Name = 'FreeLangPlus-Duployan.ttf'; Optional = $true },
    @{ From = 'checks\language_font\FreeLang_LICENSE'; Name = 'FreeLang_LICENSE' },
    @{ From = 'spacing\freelab_auto_spacing.py'; Name = 'freelab_auto_spacing.py' },
    @{ From = 'compose\freelab_glyph_compose.py'; Name = 'freelab_glyph_compose.py' },
    # Its Glyph generation tab: a helper module, no menu entry of its own (see freelab_alternates.module)
    @{ From = 'compose\freelab_glyph_generation.py'; Name = 'freelab_glyph_generation.module' },
    @{ From = 'compose\glyph_generation.json'; Name = 'glyph_generation.json' },
    @{ From = 'compose\glyph_generation_LICENSE'; Name = 'glyph_generation_LICENSE' },
    @{ From = 'compose\mark_model.json'; Name = 'mark_model.json' },
    @{ From = 'compose\glyph_names.json'; Name = 'glyph_names.json' },
    @{ From = 'compose\anchor_model.json'; Name = 'anchor_model.json' },
    @{ From = 'compose\GlyphData_LICENSE'; Name = 'GlyphData_LICENSE' },
    @{ From = 'features\freelab_feature_code.py'; Name = 'freelab_feature_code.py' },
    @{ From = 'features\freelab_feature_check.py'; Name = 'freelab_feature_check.py' },
    @{ From = 'builder\freelab_font_builder.py'; Name = 'freelab_font_builder.py' },
    # Its tracer: a helper module, no menu entry of its own (see freelab_alternates.module)
    @{ From = 'builder\freelab_trace.py'; Name = 'freelab_trace.module' },
    @{ From = 'features\ligature_model.json'; Name = 'ligature_model.json' },
    # A helper module, no script of its own: FontLab lists every .py of the folder in the Scripts menu,
    # so it goes in under the extension load_sibling (kerning/freelab_auto_kerning.py) also looks for.
    @{ From = 'features\freelab_alternates.py'; Name = 'freelab_alternates.module' },
    @{ From = 'features\alternates_model.json'; Name = 'alternates_model.json' },
    @{ From = 'spacing\reference_model.json'; Name = 'reference_model.json' },
    @{ From = 'cjk\freelab_cjk_spacing.py'; Name = 'freelab_cjk_spacing.py' },
    @{ From = 'cjk\palt_model.json'; Name = 'palt_model.json' },
    @{ From = 'cjk\hangul_model.json'; Name = 'hangul_model.json' },
    @{ From = 'cjk\freelab_cjk_vertical.py'; Name = 'freelab_cjk_vertical.py' },
    @{ From = 'cjk\vertical_model.json'; Name = 'vertical_model.json' },
    @{ From = 'tools\add_vertical_metrics.py'; Name = 'add_vertical_metrics.module' },
    @{ From = 'kerning\common_pairs.txt'; Name = 'common_pairs.txt' },
    @{ From = 'kerning\script_pairs.txt'; Name = 'script_pairs.txt' },
    @{ From = 'kerning\learned_model.json'; Name = 'learned_model.json' },
    @{ From = 'kerning\class_model.json'; Name = 'class_model.json' }
)
# Scripts FreeLab once installed under other names: removed on install and uninstall.
$retired = @('freelab_accents.py',  # Accented Glyphs, then Diacritics, now Glyph Compose
    'freelab_diacritics.py', 'freelab_diacritics.pyc',  # Diacritics, now Glyph Compose (freelab_glyph_compose.py)
    'freelab_alternates.py', 'freelab_alternates.pyc',  # listed in the menu as a script: now freelab_alternates.module
    'FreeLabAutonyms.ttf', 'FreeLabAutonyms_LICENSE',  # Font Check's first font
    'FreeLabLanguages.ttf', 'FreeLabLanguages_LICENSE',  # its second name
    'FreeLang.ttf',  # one file before it became three (FreeLang-Essential.ttf, -CJK, -Extended)
    'FreeLang-Extended.ttf',  # the third of three, before they became five (-Extended-General, and two more)
    'FreeLang-Extended-General.ttf', 'FreeLang-Extended-Mongolian-Tibetan.ttf',  # the last three's names
    'FreeLang-Extended-Duployan.ttf')  # before they became FreeLang+ (FreeLangPlus-General.ttf, and two more)
# The files FreeLab put in the Scripts folder itself before 0.3 (its own submenu since): only these are
# removed from there. The root's other files are the user's or another tool's, and some of FreeLab's
# names (character_sets.json, language_families.json) are generic enough to be someone else's.
$preSubfolder = @('freelab_dark_mode.py', 'freelab_dark_mode_settings.py')
if (-not $BinDir) { $BinDir = Join-Path $env:LOCALAPPDATA 'FreeLab\bin' }
if (-not $StateDir) { $StateDir = Join-Path $env:LOCALAPPDATA 'FreeLab' }
if (-not $RegistryKey) { $RegistryKey = 'HKCU:\Software\Fontlab\fontlab7' }
$darkWorkspace = '#fff0f0f0'  # WORKSPACE_DARK in darkmode/freelab_dark_mode.py
$source = [System.IO.File]::ReadAllText((Join-Path $repo 'darkmode\native\freelab_pixels.c'))
$pixelsVersion = [regex]::Match($source, '#define FREELAB_PIXELS_VERSION (\d+)').Groups[1].Value
$nativeName = 'freelab_pixels-v' + $pixelsVersion + '.dll'
# The native engine's library (darkmode/native/freelab_hooks.c), named after both versions.
$hooksSource = [System.IO.File]::ReadAllText((Join-Path $repo 'darkmode\native\freelab_hooks.c'))
$hooksName = 'freelab_hooks-v' + [regex]::Match($hooksSource, '#define FREELAB_HOOKS_VERSION (\d+)').Groups[1].Value + '-' + $pixelsVersion + '.dll'
# The auto kerning core (kerning/native/freelab_kern.c).
$kernSource = [System.IO.File]::ReadAllText((Join-Path $repo 'kerning\native\freelab_kern.c'))
$kernName = 'freelab_kern-v' + [regex]::Match($kernSource, '#define FREELAB_KERN_VERSION (\d+)').Groups[1].Value + '.dll'
$begin = '# >>> FreeLab tools'
$end = '# <<< FreeLab tools'

# FreeLab's markers are whole lines, from the start of the line. A line starting "# >>> FreeLab" opens a
# block and one starting "# <<< FreeLab" closes it, in turn; a block of this installer's opens with
# $begin alone or followed by a space and a note, and closes with $end alone. Marker text anywhere else
# (a string in the user's code, an indented comment) is the user's, never a marker. This one recognizer
# serves the check and every change: the check once took markers at the start of a line while the
# changes took marker text anywhere, and deleted the user's code between two quoted markers.
$ownOpen = '^' + [regex]::Escape($begin) + '(?:[ \t].*)?$'
$ownClose = '^' + [regex]::Escape($end) + '[ \t]*$'
# The one block FreeLab wrote before the MCP and the tools became separate repositories
# (dark mode and the listener together). Either installer takes it out and says so.
$legacyOpen = '^# >>> FreeLab \(managed.*$'
$legacyClose = '^# <<< FreeLab[ \t]*$'

# The blocks a pair of markers delimits, as (first line, last line) index pairs; $null when the file's
# FreeLab markers do not pair: a block opened inside another, closed without being opened, never
# closed, or opened by one kind of marker and closed by another (another FreeLab block's markers count).
function Find-Blocks([string[]]$lines, [string]$open, [string]$close) {
    $found = New-Object System.Collections.ArrayList
    $start = -1
    $mine = $false
    for ($i = 0; $i -lt $lines.Length; $i++) {
        $line = $lines[$i]
        if ($line.StartsWith('# >>> FreeLab', [System.StringComparison]::Ordinal)) {
            if ($start -ge 0) { return $null }
            $start = $i
            $mine = $line -cmatch $open
        }
        elseif ($line.StartsWith('# <<< FreeLab', [System.StringComparison]::Ordinal)) {
            if ($start -lt 0) { return $null }
            if (($line -cmatch $close) -ne $mine) { return $null }
            if ($mine) { [void]$found.Add(@($start, $i)) }
            $start = -1
        }
    }
    if ($start -ge 0) { return $null }
    return ,$found
}

function Split-Lines([string]$text) { return ,$text.Split([char]10) }

# The text without the blocks of that kind (the lines between their markers, markers included).
function Remove-Blocks([string]$text, [string]$open, [string]$close) {
    $lines = Split-Lines $text
    $blocks = Find-Blocks $lines $open $close
    if ($null -eq $blocks) { throw "unpaired FreeLab markers" }  # (checked before: never reached)
    $drop = @{}
    foreach ($block in $blocks) { for ($i = $block[0]; $i -le $block[1]; $i++) { $drop[$i] = $true } }
    $kept = New-Object System.Collections.Generic.List[string]
    for ($i = 0; $i -lt $lines.Length; $i++) { if (-not $drop.ContainsKey($i)) { $kept.Add($lines[$i]) } }
    return ([string]::Join("`n", $kept)).TrimEnd("`n") + "`n"
}

function Remove-Block([string]$text) { return Remove-Blocks $text $ownOpen $ownClose }

# The block put where it already is (the other repository's block keeps its place), or appended.
function Set-Block([string]$text, [string]$newBlock) {
    $lines = Split-Lines $text
    $blocks = Find-Blocks $lines $ownOpen $ownClose
    if ($null -eq $blocks) { throw "unpaired FreeLab markers" }  # (checked before: never reached)
    if ($blocks.Count -gt 0) {
        # the first copy replaced, any later one (a duplicated block) taken out
        $drop = @{}
        foreach ($block in $blocks) { for ($i = $block[0]; $i -le $block[1]; $i++) { $drop[$i] = $true } }
        $kept = New-Object System.Collections.Generic.List[string]
        for ($i = 0; $i -lt $lines.Length; $i++) {
            if ($i -eq $blocks[0][0]) { $kept.Add($newBlock) }
            elseif (-not $drop.ContainsKey($i)) { $kept.Add($lines[$i]) }
        }
        return [string]::Join("`n", $kept)
    }
    $text = $text.TrimEnd("`n")
    if ($text) { $text += "`n" }
    return $text + $newBlock + "`n"
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

# FontLab's startup script is read as strict UTF-8 (a BOM is kept) and written back with its own
# line endings, and only when it changes. A file that is not UTF-8, or whose FreeLab markers are
# not paired, is left alone: rewriting it would replace characters or delete the user's code.
$current = ''
$normalized = ''
$notUtf8 = $false
$bom = $false
$crlf = $false
if (Test-Path $startup) {
    $bytes = [System.IO.File]::ReadAllBytes($startup)
    $bom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
    $skip = 0
    if ($bom) { $skip = 3 }
    $strict = New-Object System.Text.UTF8Encoding $false, $true
    $original = $null
    try { $original = $strict.GetString($bytes, $skip, $bytes.Length - $skip) }
    catch {
        # Not UTF-8 (an ANSI file with a coding line, say): read as ASCII only to look for FreeLab's markers.
        # With none, there is nothing of FreeLab's in it, and it is changed only if this run must add a block.
        if ([System.Text.Encoding]::ASCII.GetString($bytes).Contains('# >>> FreeLab') -or
            [System.Text.Encoding]::ASCII.GetString($bytes).Contains('# <<< FreeLab')) {
            Write-Output "$startup is not UTF-8 text and holds a FreeLab block, so it is left as it is. Save it as UTF-8 and run this again."
            exit 1
        }
        $notUtf8 = $true
    }
    if ($null -ne $original) {
        $crlf = $original.Contains("`r`n")
        $normalized = $original -replace "`r`n", "`n"
        $current = $normalized
    }
}
# Each begin marker must be followed by its own end marker before the next begin: counting them was not
# enough (an end marker above its begin marker let a later install delete the code between them).
$currentLines = Split-Lines $current
if ($null -eq (Find-Blocks $currentLines $ownOpen $ownClose) -or $null -eq (Find-Blocks $currentLines $legacyOpen $legacyClose)) {
    Write-Output "$startup has a FreeLab begin marker without its end marker, or the reverse, or two blocks' markers mixed, so it is left as it is. Remove the broken block by hand and run this again."
    exit 1
}
function Test-Changed([string]$text) {
    return $text.TrimEnd("`n") -ne $normalized.TrimEnd("`n")
}
function Save-Startup([string]$text) {
    if ($notUtf8) {
        Write-Output "$startup is not UTF-8 text, so the FreeLab block was not added. Save it as UTF-8 and run this again."
        exit 1
    }
    if ((Test-Path $startup) -and -not (Test-Path "$startup.freelab-backup")) {
        [System.IO.File]::Copy($startup, "$startup.freelab-backup")
        Write-Host "Kept the original startup script as $startup.freelab-backup"
    }
    $folder = Split-Path -Parent $startup
    if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Path $folder | Out-Null }
    if ($crlf) { $text = $text -replace "`n", "`r`n" }
    # Written whole beside it, then put in its place, the file it replaces kept as .freelab-previous
    # (each update: the first install's copy is the user's file before FreeLab, not their later changes)
    $temp = "$startup.freelab-new"
    try {
        [System.IO.File]::WriteAllText($temp, $text, (New-Object System.Text.UTF8Encoding $bom))
        if ([System.IO.File]::Exists($startup)) { [System.IO.File]::Replace($temp, $startup, "$startup.freelab-previous", $true) }
        else { [System.IO.File]::Move($temp, $startup) }
    }
    catch {
        if ([System.IO.File]::Exists($temp)) { [System.IO.File]::Delete($temp) }
        Write-Output "Could not write ${startup}: $($_.Exception.Message) It is left as it was."
        exit 1
    }
}
if (-not $Uninstall -and -not (Test-Path $startup)) {
    # FontLab writes its own startup script (its default imports) when it first starts; one made here
    # holding only this block could keep FontLab from writing it.
    Write-Output "FontLab has not made its startup script yet ($startup): start FontLab once, quit it, and run this again."
    exit 1
}
$legacy = (Find-Blocks $currentLines $legacyOpen $legacyClose).Count -gt 0
if ($legacy) { $current = Remove-Blocks $current $legacyOpen $legacyClose }
function Write-LegacyNote {
    if ($legacy) {
        Write-Output 'Removed the combined FreeLab block of earlier versions, which also started the MCP listener. To keep that, run tools\install-fontlab.ps1 -ListenerAtLaunch from FreeLab MCP.'
    }
}

# What an install or uninstall could not do. $incomplete: required (a script or its data, the auto
# kerning core, anything an uninstall leaves behind): listed at the end, and the exit status is 1.
# $degraded: expected, and FreeLab works without it (a font FontLab registered and holds open until
# it quits, which the next install replaces): said, the exit status stays 0.
$incomplete = New-Object System.Collections.ArrayList
$degraded = New-Object System.Collections.ArrayList

# The reason a file operation failed, in words: "in use" for a sharing or lock violation (FontLab holds
# the file), else the error's own message (access denied, a missing folder, a full disk).
function Get-Reason($record) {
    $ex = $record.Exception
    while ($null -ne $ex.InnerException) { $ex = $ex.InnerException }
    $code = $ex.HResult -band 0xFFFF
    if ($code -eq 32 -or $code -eq 33) { return 'in use by another program, FontLab if it runs' }
    return $ex.Message.Trim()
}

function Add-Incomplete([string]$what) { [void]$incomplete.Add($what); Write-Output "Could not $what" }

function Write-Summary {
    if ($degraded.Count -gt 0) {
        Write-Output ("Left for the next install (FreeLab works without them meanwhile): " + ($degraded -join '; ') + '.')
    }
    if ($incomplete.Count -gt 0) {
        Write-Output ("Not done (" + $incomplete.Count + "): " + ($incomplete -join '; ') + '. Quit FontLab if it runs, deal with the reason given, and run this again.')
        exit 1
    }
}

if ($Uninstall) {
    # Dark mode keeps FontLab's own workspace color in darkmode.json while it is on.
    $settingsFile = Join-Path $StateDir 'darkmode.json'
    if (Test-Path $settingsFile) {
        $saved = $null
        try { $saved = ([System.IO.File]::ReadAllText($settingsFile) | ConvertFrom-Json).saved_workspace } catch { }
        if ($saved -and (Get-Process -Name $ProcessName -ErrorAction SilentlyContinue)) {
            Write-Output 'FontLab is running with dark mode on: switch dark mode off (Scripts > FreeLab > Dark Mode), quit FontLab, and run -Uninstall again.'
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
    if (Test-Path "$settingsFile.tmp") { [System.IO.File]::Delete("$settingsFile.tmp") }  # a save cut short
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
    # Auto Kerning's remembered analyses.
    $kernCache = Join-Path $StateDir 'kerning-cache'
    if (Test-Path $kernCache) { [System.IO.Directory]::Delete($kernCache, $true); Write-Output "Removed $kernCache" }
    # The size given to the tools' windows by hand, and Proof's summary settings.
    foreach ($name in @('windows.json', 'proof.json')) {
        $kept = Join-Path $StateDir $name
        if (Test-Path $kept) {
            try { [System.IO.File]::Delete($kept); Write-Output "Removed $kept" }
            catch { Add-Incomplete "remove $kept ($(Get-Reason $_))" }
        }
    }
    $installed = @(@($files | ForEach-Object { Join-Path $scripts $_.Name }) + @($retired | ForEach-Object { Join-Path $scripts $_ }) +
        @($preSubfolder | ForEach-Object { Join-Path $rootScripts $_ }))  # (the Scripts folder itself held these before 0.3)
    foreach ($target in $installed) {
        if (Test-Path $target) {
            try { [System.IO.File]::Delete($target); Write-Output "Removed $target" }
            catch { Add-Incomplete "remove $target ($(Get-Reason $_))" }
        }
    }
    if ((Test-Path $scripts) -and -not (Get-ChildItem $scripts -Force)) {
        [System.IO.Directory]::Delete($scripts); Write-Output "Removed $scripts"
    }
    if (Test-Path $BinDir) {
        foreach ($dll in @(Get-ChildItem $BinDir -Filter 'freelab_pixels*.dll') + @(Get-ChildItem $BinDir -Filter 'freelab_hooks*.dll') + @(Get-ChildItem $BinDir -Filter 'freelab_kern*.dll')) {
            try { [System.IO.File]::Delete($dll.FullName); Write-Output "Removed $($dll.FullName)" }
            catch { Add-Incomplete "remove $($dll.FullName) ($(Get-Reason $_))" }
        }
    }
    Write-Summary
    exit 0
}

# The scripts and their data staged first, each beside its place (.freelab-new): a file that cannot even
# be staged stops the install before anything installed is replaced. Then each takes its place. A
# font is the one expected failure: FontLab holds the fonts it registered open until it quits, and the
# installed copy serves meanwhile. Anything else that fails stops the install before the old files are
# retired and the startup block is written, so no new script runs beside old data.
function Test-Font([string]$name) { return $name.EndsWith('.ttf', [System.StringComparison]::OrdinalIgnoreCase) }
if (-not (Test-Path $scripts)) { New-Item -ItemType Directory -Path $scripts | Out-Null }
$staged = New-Object System.Collections.ArrayList
foreach ($f in $files) {
    $target = Join-Path $scripts $f.Name
    $from = Join-Path $repo $f.From
    if ($f.Optional -and -not (Test-Path $from)) { Write-Output "Skipped $($f.Name) (optional, not in this copy)"; continue }
    # A file already there as it is stays (FontLab holds a font it registered open: it could not be replaced)
    $same = (Test-Path $target) -and ((Get-FileHash $from).Hash -eq (Get-FileHash $target).Hash)
    if ($same) { Write-Output "Kept $($f.Name) (unchanged)"; continue }
    $temp = "$target.freelab-new"
    try {
        [System.IO.File]::Copy($from, $temp, $true)
        [void]$staged.Add(@{ Name = $f.Name; Temp = $temp; Target = $target })
    }
    catch { Add-Incomplete "copy $($f.Name) to $scripts ($(Get-Reason $_))" }
}
# Each installed file to be replaced opened alone first: one another program holds (FontLab, a font it
# registered; an editor) is found before anything is replaced, not halfway.
$replace = New-Object System.Collections.ArrayList
foreach ($s in $staged) {
    if ([System.IO.File]::Exists($s.Target)) {
        try { [System.IO.File]::Open($s.Target, 'Open', 'ReadWrite', 'None').Close() }
        catch {
            $reason = Get-Reason $_
            [System.IO.File]::Delete($s.Temp)
            if (Test-Font $s.Name) {
                [void]$degraded.Add("$($s.Name), the earlier copy kept ($reason)")
                Write-Output "Could not replace $($s.Name) ($reason): the earlier copy stays until the next install."
            }
            else { Add-Incomplete "replace $($s.Name) in $scripts ($reason)" }
            continue
        }
    }
    [void]$replace.Add($s)
}
if ($incomplete.Count -gt 0) {
    foreach ($s in $staged) { if ([System.IO.File]::Exists($s.Temp)) { [System.IO.File]::Delete($s.Temp) } }
    Write-Output 'Nothing installed was replaced.'
    Write-Summary
}
foreach ($s in $replace) {
    try {
        if ([System.IO.File]::Exists($s.Target)) { [System.IO.File]::Replace($s.Temp, $s.Target, [NullString]::Value, $true) }
        else { [System.IO.File]::Move($s.Temp, $s.Target) }
        Write-Output "Copied $($s.Name) to $scripts"
    }
    catch {
        $reason = Get-Reason $_
        if ([System.IO.File]::Exists($s.Temp)) { [System.IO.File]::Delete($s.Temp) }
        if (Test-Font $s.Name) {
            [void]$degraded.Add("$($s.Name), the earlier copy kept ($reason)")
            Write-Output "Could not replace $($s.Name) ($reason): the earlier copy stays until the next install."
        }
        else { Add-Incomplete "replace $($s.Name) in $scripts ($reason)" }
    }
}
if ($incomplete.Count -gt 0) {
    Write-Output 'FreeLab is partly installed: the files above were not replaced, so nothing was retired and the startup block was not written.'
    Write-Summary
}
foreach ($name in $preSubfolder) {  # before 0.3 they sat in the Scripts folder itself
    $old = Join-Path $rootScripts $name
    if (Test-Path $old) {
        try { [System.IO.File]::Delete($old); Write-Output "Removed the old $old" }
        catch { Add-Incomplete "remove the old $old ($(Get-Reason $_))" }
    }
}
foreach ($name in $retired) {
    $old = Join-Path $scripts $name
    if (Test-Path $old) {
        try { [System.IO.File]::Delete($old); Write-Output "Removed the retired $old" }
        catch {
            $reason = Get-Reason $_
            if (Test-Font $name) {
                [void]$degraded.Add("the retired $name ($reason)")
                Write-Output "Could not remove the retired $old ($reason): the next install removes it."
            }
            else { Add-Incomplete "remove the retired $old ($reason)" }
        }
    }
}

$native = Join-Path $BinDir $nativeName
if (Test-Path $native) { Write-Output "Native helper present: $native" }
else {
    try { & (Join-Path $PSScriptRoot 'build-native.ps1') -Out $native }
    catch {
        Write-Output "Could not build the native helper: $_"
        Write-Output 'Dark mode still works, with plain inversion in the widgets FontLab paints itself. Install LLVM or Visual Studio with the C++ tools, then run tools\build-native.ps1.'
        [void]$degraded.Add('the native pixel helper (dark mode inverts plainly without it)')
    }
}
$hooks = Join-Path $BinDir $hooksName
if (Test-Path $hooks) { Write-Output "Native engine present: $hooks" }
elseif (Test-Path $native) {  # the same compiler builds it
    try { & (Join-Path $PSScriptRoot 'build-native.ps1') -Hooks -Out $hooks }
    catch { Write-Output "Could not build the native engine: $_ (the script engine still works)." }
}
$kern = Join-Path $BinDir $kernName
if (Test-Path $kern) { Write-Output "Auto kerning core present: $kern" }
elseif (Test-Path $native) {  # the same compiler builds it
    try { & (Join-Path $PSScriptRoot 'build-native.ps1') -Kern -Out $kern }
    catch { Write-Output "Could not build the auto kerning core: $_" }
}
if (-not (Test-Path $kern)) {  # (required: Auto Kerning, Auto Spacing, Kerning Check, and Glyph Compose measure with it)
    Add-Incomplete "build the auto kerning core $kernName, which Auto Kerning, Auto Spacing, Kerning Check, and Glyph Compose measure with (it needs a C compiler: LLVM or Visual Studio with the C++ tools; then tools\build-native.ps1 -Kern)"
}
if ((Test-Path $native) -and (Test-Path $BinDir)) {
    # Earlier versions: FontLab keeps the one it loaded locked until it quits, so a locked one waits for the next install.
    foreach ($dll in @(Get-ChildItem $BinDir -Filter 'freelab_pixels*.dll') + @(Get-ChildItem $BinDir -Filter 'freelab_hooks*.dll') + @(Get-ChildItem $BinDir -Filter 'freelab_kern*.dll')) {
        if ($dll.Name -eq $nativeName -or $dll.Name -eq $hooksName -or $dll.Name -eq $kernName) { continue }
        try { [System.IO.File]::Delete($dll.FullName); Write-Output "Removed the superseded $($dll.FullName)" } catch { }
    }
}

$darkPath = ConvertTo-PyLiteral (Join-Path $scripts 'freelab_dark_mode.py')
$kernPath = ConvertTo-PyLiteral (Join-Path $scripts 'freelab_auto_kerning.py')
$tabsPath = ConvertTo-PyLiteral (Join-Path $scripts 'freelab_tabs.py')
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
$end
"@ -replace "`r`n", "`n"

$text = Set-Block $current $block
if (Test-Changed $text) {
    Save-Startup $text
    Write-Output "Added the FreeLab tools block to $startup"
    Write-LegacyNote
}
else { Write-Output "The FreeLab tools block in $startup is up to date" }
Write-Summary

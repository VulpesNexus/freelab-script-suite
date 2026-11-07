# Build darkmode/native/freelab_pixels.c into a 64-bit DLL for FontLab's Python.
#
#   build-native.ps1 [-Out <path>] [-Hooks]
#
# -Hooks builds the experimental native dark mode instead (darkmode/native/freelab_hooks.c, which
# includes freelab_pixels.c), into freelab_hooks-v<version>.dll.
#
# The default output is %LOCALAPPDATA%\FreeLab\bin\freelab_pixels-v<version>.dll, where the
# dark-mode script looks for it. Without the DLL, dark mode still works, with
# plain color inversion (hue flipped) in the few widgets FontLab paints itself.
# Uses clang (LLVM) if present, else MSVC through vswhere. The build runs in a
# temporary ASCII folder: native tools fail under the workspace's non-ASCII path.
#
# ASCII only: Windows PowerShell 5.1 reads a BOM-less script in the ANSI code page.

param([string]$Out, [switch]$Hooks)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repo 'darkmode\native\freelab_pixels.c'
$name = if ($Hooks) { 'freelab_hooks' } else { 'freelab_pixels' }
$match = [regex]::Match([System.IO.File]::ReadAllText($source), '#define FREELAB_PIXELS_VERSION (\d+)')
if (-not $match.Success) { throw 'FREELAB_PIXELS_VERSION not found in freelab_pixels.c' }
# Versioned name: FontLab keeps a loaded DLL locked, so a newer build must not need the same file.
$version = $match.Groups[1].Value
if ($Hooks) {
    # Named after both versions: FontLab keeps a loaded library locked, and the hooks change on their own.
    $hooksMatch = [regex]::Match([System.IO.File]::ReadAllText((Join-Path $repo 'darkmode\native\freelab_hooks.c')), '#define FREELAB_HOOKS_VERSION (\d+)')
    if (-not $hooksMatch.Success) { throw 'FREELAB_HOOKS_VERSION not found in freelab_hooks.c' }
    $version = $hooksMatch.Groups[1].Value + '-' + $version
}
if (-not $Out) { $Out = Join-Path $env:LOCALAPPDATA ('FreeLab\bin\' + $name + '-v' + $version + '.dll') }
$work = Join-Path ([System.IO.Path]::GetTempPath()) ('freelab-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
try {
    Copy-Item $source $work
    if ($Hooks) { Copy-Item (Join-Path $repo 'darkmode\native\freelab_hooks.c') $work }
    Push-Location $work
    try {
        $clang = Get-Command clang -ErrorAction SilentlyContinue
        if (-not $clang -and (Test-Path 'C:\Program Files\LLVM\bin\clang.exe')) { $clang = Get-Item 'C:\Program Files\LLVM\bin\clang.exe' }
        if ($clang) {
            $exe = if ($clang.Source) { $clang.Source } else { $clang.FullName }
            & $exe -O2 -shared -m64 -nostdlib -fno-builtin '-Wl,/noentry' -o "$name.dll" "$name.c"
        } else {
            $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
            $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
            if (-not $vs) { throw 'No compiler found: install LLVM (clang) or Visual Studio with the C++ tools.' }
            $vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'
            cmd.exe /d /c "`"$vcvars`" >nul && cl /nologo /O2 /GS- /LD $name.c /Fe$name.dll /link /NODEFAULTLIB /NOENTRY"
        }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$name.dll")) { throw "The compiler failed (exit $LASTEXITCODE)." }
    } finally { Pop-Location }
    $folder = Split-Path -Parent $Out
    if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Path $folder | Out-Null }
    [System.IO.File]::Copy((Join-Path $work "$name.dll"), $Out, $true)
    Write-Output "Built $Out"
} finally {
    [System.IO.Directory]::Delete($work, $true)
}

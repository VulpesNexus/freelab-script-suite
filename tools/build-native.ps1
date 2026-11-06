# Build darkmode/native/freelab_pixels.c into a 64-bit DLL for FontLab's Python.
#
#   build-native.ps1 [-Out <path>]
#
# The default output is %LOCALAPPDATA%\FreeLab\bin\freelab_pixels-v<version>.dll, where the
# dark-mode script looks for it. Without the DLL, dark mode still works, with
# plain color inversion (hue flipped) in the few widgets FontLab paints itself.
# Uses clang (LLVM) if present, else MSVC through vswhere. The build runs in a
# temporary ASCII folder: native tools fail under the workspace's non-ASCII path.
#
# ASCII only: Windows PowerShell 5.1 reads a BOM-less script in the ANSI code page.

param([string]$Out)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repo 'darkmode\native\freelab_pixels.c'
$match = [regex]::Match([System.IO.File]::ReadAllText($source), '#define FREELAB_PIXELS_VERSION (\d+)')
if (-not $match.Success) { throw 'FREELAB_PIXELS_VERSION not found in freelab_pixels.c' }
# Versioned name: FontLab keeps a loaded DLL locked, so a newer build must not need the same file.
if (-not $Out) { $Out = Join-Path $env:LOCALAPPDATA ('FreeLab\bin\freelab_pixels-v' + $match.Groups[1].Value + '.dll') }
$work = Join-Path ([System.IO.Path]::GetTempPath()) ('freelab-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
try {
    Copy-Item $source $work
    Push-Location $work
    try {
        $clang = Get-Command clang -ErrorAction SilentlyContinue
        if (-not $clang -and (Test-Path 'C:\Program Files\LLVM\bin\clang.exe')) { $clang = Get-Item 'C:\Program Files\LLVM\bin\clang.exe' }
        if ($clang) {
            $exe = if ($clang.Source) { $clang.Source } else { $clang.FullName }
            & $exe -O2 -shared -m64 -nostdlib -fno-builtin '-Wl,/noentry' -o freelab_pixels.dll freelab_pixels.c
        } else {
            $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
            $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
            if (-not $vs) { throw 'No compiler found: install LLVM (clang) or Visual Studio with the C++ tools.' }
            $vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'
            cmd.exe /d /c "`"$vcvars`" >nul && cl /nologo /O2 /GS- /LD freelab_pixels.c /Fefreelab_pixels.dll /link /NODEFAULTLIB /NOENTRY"
        }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path freelab_pixels.dll)) { throw "The compiler failed (exit $LASTEXITCODE)." }
    } finally { Pop-Location }
    $folder = Split-Path -Parent $Out
    if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Path $folder | Out-Null }
    [System.IO.File]::Copy((Join-Path $work 'freelab_pixels.dll'), $Out, $true)
    Write-Output "Built $Out"
} finally {
    [System.IO.Directory]::Delete($work, $true)
}

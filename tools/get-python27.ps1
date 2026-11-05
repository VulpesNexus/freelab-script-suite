# Fetch the Python Software Foundation's Python 2.7.18 (64-bit) NuGet package
# into %LOCALAPPDATA%\FreeLab\python27, for testing the listener under the
# Python that FontLab 7 embeds. Nothing is installed: no registry, no PATH.
#
# It does not go inside the repository: Python 2.7 opens files through the
# ANSI code page, so it cannot start from a folder whose path that code page
# cannot encode. Set FREELAB_PY27_DIR to put it somewhere else.
#
# The package hash is checked against the SHA-512 that nuget.org publishes.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ($env:FREELAB_PY27_DIR) { $dest = $env:FREELAB_PY27_DIR }
else { $dest = Join-Path $env:LOCALAPPDATA 'FreeLab\python27' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
$version = '2.7.18'
$expected = 'CoiwtlbQcWAxsvXGcv7vPkZtzHhNwrR5HgniC+bbQJdiEn3GbI/zA7Kku5NP9HYVKMO+KMZrgBnigPgsc68zyA=='

if (Test-Path (Join-Path $dest 'tools\python.exe')) {
    Write-Output "Python $version is already in $dest"
    exit 0
}

$download = Join-Path ([System.IO.Path]::GetTempPath()) ("freelab-python2-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $download | Out-Null
try {
    $nupkg = Join-Path $download "python2.$version.nupkg"
    Invoke-WebRequest "https://api.nuget.org/v3-flatcontainer/python2/$version/python2.$version.nupkg" -OutFile $nupkg -UseBasicParsing -TimeoutSec 600

    $sha = [System.Security.Cryptography.SHA512]::Create()
    $stream = [System.IO.File]::OpenRead($nupkg)
    try { $actual = [Convert]::ToBase64String($sha.ComputeHash($stream)) } finally { $stream.Dispose() }
    if ($actual -ne $expected) { throw "Package hash mismatch: $actual" }

    $staging = "$dest.partial"
    if (Test-Path $staging) { [System.IO.Directory]::Delete($staging, $true) }
    if (Test-Path $dest) { [System.IO.Directory]::Delete($dest, $true) }  # left by an interrupted run
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($nupkg, $staging)
    [System.IO.Directory]::Move($staging, $dest)
    Write-Output "Python $version extracted to $dest"
}
finally {
    [System.IO.Directory]::Delete($download, $true)
}

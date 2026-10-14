$projectRoot = (Get-Location).Path
if (-not $projectRoot) {
    $projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$buildRoot = Join-Path $projectRoot "build"
$distRoot = Join-Path $projectRoot "dist"
$releaseVersion = "v1.0.4"
$releaseStamp = Get-Date -Format "yyyyMMdd"
$releaseZipBase = "485experiment-software-portable-$releaseVersion-$releaseStamp"
$releaseZipName = "$releaseZipBase.zip"

Set-Location $projectRoot

foreach ($cleanupPath in @($buildRoot, $distRoot)) {
    if (Test-Path $cleanupPath) {
        $resolvedCleanup = (Resolve-Path $cleanupPath).Path
        if (-not $resolvedCleanup.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to delete unexpected path: $resolvedCleanup"
        }
        Get-ChildItem -Path $resolvedCleanup -Force | Remove-Item -Recurse -Force
    }
}

py -3 -m pip install -r requirements.txt
py -3 -m pip install pyinstaller
py -3 -m PyInstaller .\app_launcher.spec --noconfirm

$appDist = Get-ChildItem -Path $distRoot -Directory | Select-Object -First 1
if (-not $appDist) {
    throw "Portable release folder was not created."
}

foreach ($folderName in @("logs", "output", "videos")) {
    $folderPath = Join-Path $appDist.FullName $folderName
    if (-not (Test-Path $folderPath)) {
        New-Item -ItemType Directory -Path $folderPath | Out-Null
    }
}

Copy-Item -Path (Join-Path $projectRoot "config") -Destination (Join-Path $appDist.FullName "config") -Recurse -Force
Copy-Item -Path (Join-Path $projectRoot "README_portable.txt") -Destination (Join-Path $appDist.FullName "README.txt") -Force
# Find the manual PDF via wildcard — the literal Chinese filename in this
# UTF-8-encoded script is not the same byte sequence as the GBK-encoded
# filename on disk, so Test-Path / Join-Path (which use the in-memory
# UTF-8 string) cannot find it.  Get-ChildItem goes through the Windows
# native filesystem layer and resolves to the GBK path correctly.
# We also avoid putting Chinese inside the -Filter string (the filter is
# compared by the Windows shell, and a UTF-8 in-script string would not
# match the GBK on-disk name); matching by extension is sufficient since
# there is only one PDF in the project root.
$manualPdf = Get-ChildItem -Path $projectRoot -Filter '*.pdf' -ErrorAction SilentlyContinue | Select-Object -First 1
Write-Host "DEBUG manualPdf: $($manualPdf.FullName)"
if ($manualPdf) {
    Copy-Item -Path $manualPdf.FullName -Destination (Join-Path $appDist.FullName $manualPdf.Name) -Force
    Write-Host "DEBUG Copy-Item exit: $LASTEXITCODE"
}
if (Test-Path (Join-Path $projectRoot "GROUPED_MEASUREMENT_GUIDE.txt")) {
    Copy-Item -Path (Join-Path $projectRoot "GROUPED_MEASUREMENT_GUIDE.txt") -Destination (Join-Path $appDist.FullName "GROUPED_MEASUREMENT_GUIDE.txt") -Force
}

$releaseZipPath = Join-Path $projectRoot $releaseZipName
if (Test-Path $releaseZipPath) {
    Remove-Item $releaseZipPath -Force
}
Compress-Archive -Path (Join-Path $appDist.FullName "*") -DestinationPath $releaseZipPath -Force

Write-Host "Portable release created at: $($appDist.FullName)"
Write-Host "Release archive: $releaseZipPath"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildRoot = Join-Path $projectRoot "build"
$distRoot = Join-Path $projectRoot "dist"
$releaseVersion = "v1.0.2"
$releaseDate = Get-Date -Format "yyyyMMdd"
$zipName = "485experiment-software-portable-$releaseVersion-$releaseDate.zip"

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
Copy-Item -Path (Join-Path $projectRoot "docs\portable-grouped-measurement-guide.txt") -Destination (Join-Path $appDist.FullName "GROUPED_MEASUREMENT_GUIDE.txt") -Force

Write-Host "Portable release created at: $($appDist.FullName)"

$zipPath = Join-Path $distRoot $zipName
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path (Join-Path $appDist.FullName '*') -DestinationPath $zipPath
Write-Host "Portable release zip created at: $zipPath"

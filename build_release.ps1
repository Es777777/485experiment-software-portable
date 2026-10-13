$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
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

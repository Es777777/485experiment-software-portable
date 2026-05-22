$ErrorActionPreference = 'Stop'

function Get-MachinePathParts {
    $path = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    if ([string]::IsNullOrWhiteSpace($path)) {
        return @()
    }
    return $path.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries)
}

function Set-MachinePathParts($parts) {
    $joined = ($parts | Select-Object -Unique) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $joined, 'Machine')
}

$cuda13Root = 'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0'
$removePaths = @(
    'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin\x64',
    'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin'
)

Write-Host 'Removing machine CUDA 13 environment variables...'
[Environment]::SetEnvironmentVariable('CUDA_PATH', $null, 'Machine')
[Environment]::SetEnvironmentVariable('CUDA_PATH_V13_0', $null, 'Machine')

Write-Host 'Cleaning CUDA 13 entries from machine PATH...'
$newParts = Get-MachinePathParts | Where-Object { $_ -and ($_ -notin $removePaths) }
Set-MachinePathParts $newParts

Write-Host 'Trying to uninstall system CUDA 13.0...'
winget uninstall --id Nvidia.CUDA --accept-source-agreements

if (Test-Path $cuda13Root) {
    Write-Host 'Removing leftover CUDA 13 folder...'
    Remove-Item -LiteralPath $cuda13Root -Recurse -Force
}

Write-Host 'Done. Reopen your terminal and verify with:'
Write-Host '  where nvcc'
Write-Host '  nvcc --version'
Write-Host "  powershell -NoProfile -Command \"Get-ChildItem Env:CUDA*\""

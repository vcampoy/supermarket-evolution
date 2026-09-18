Set-StrictMode -Version Latest

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Get-BackendDirectory([string] $ConfiguredPath) {
    if ($ConfiguredPath) { return (Resolve-Path $ConfiguredPath).Path }
    return (Join-Path (Get-ProjectRoot) "src\backend")
}

function Get-OperationalLogPath([string] $LogDirectory, [string] $Name) {
    $directory = [IO.Path]::GetFullPath($LogDirectory)
    if (-not (Test-Path -LiteralPath $directory)) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
    return (Join-Path $directory $Name)
}

function Rotate-OperationalLog([string] $Path, [int] $MaxBytes = 5242880, [int] $Keep = 5) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    if ((Get-Item -LiteralPath $Path).Length -lt $MaxBytes) { return }
    for ($index = $Keep - 1; $index -ge 1; $index--) {
        $source = "$Path.$index"
        $target = "$Path.$($index + 1)"
        if (Test-Path -LiteralPath $source) { Move-Item -LiteralPath $source -Destination $target -Force }
    }
    Move-Item -LiteralPath $Path -Destination "$Path.1" -Force
}

function Write-OperationalLog([string] $Path, [string] $Event, [string] $Status, [string] $Detail = "") {
    $timestamp = [DateTime]::UtcNow.ToString("o")
    $safeDetail = $Detail -replace "(?i)(authorization|token|secret|password)\s*[:=]\s*\S+", '$1=[redacted]'
    "$timestamp`t$Event`t$Status`t$safeDetail" | Add-Content -LiteralPath $Path -Encoding UTF8
}

function Get-BackendPython([string] $BackendDirectory, [string] $ConfiguredPython) {
    if ($ConfiguredPython) { return $ConfiguredPython }
    $venvPython = Join-Path $BackendDirectory ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) { return $venvPython }
    return "python"
}

function Activate-BackendEnvironment([string] $BackendDirectory) {
    $activate = Join-Path $BackendDirectory ".venv\Scripts\Activate.ps1"
    if (Test-Path -LiteralPath $activate) { . $activate }
}

function Test-TailscaleIPv4([string] $Address) {
    $parsed = $null
    if (-not [Net.IPAddress]::TryParse($Address, [ref] $parsed)) { return $false }
    if ($parsed.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    $bytes = $parsed.GetAddressBytes()
    return ($bytes[0] -eq 100 -and $bytes[1] -ge 64 -and $bytes[1] -le 127)
}

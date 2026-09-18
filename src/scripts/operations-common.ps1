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
    $candidates = @()
    if ($ConfiguredPython) {
        $candidates += $ConfiguredPython
    }
    else {
        $candidates += (Join-Path $BackendDirectory ".venv\Scripts\python.exe")
        # Compatibility with the environment used before .venv became the documented standard.
        $candidates += (Join-Path $BackendDirectory ".venv313\Scripts\python.exe")
        $candidates += "python"
    }

    foreach ($candidate in $candidates) {
        if ([IO.Path]::IsPathRooted($candidate) -and -not (Test-Path -LiteralPath $candidate)) {
            continue
        }
        try {
            $version = (& $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null | Select-Object -Last 1)
            if ($LASTEXITCODE -eq 0 -and $version -eq "3.13") { return $candidate }
        }
        catch {
            continue
        }
    }

    throw "Python 3.13 is required. From src\backend run: uv venv --clear --python 3.13 --seed .venv"
}

function Test-TailscaleIPv4([string] $Address) {
    $parsed = $null
    if (-not [Net.IPAddress]::TryParse($Address, [ref] $parsed)) { return $false }
    if ($parsed.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { return $false }
    $bytes = $parsed.GetAddressBytes()
    return ($bytes[0] -eq 100 -and $bytes[1] -ge 64 -and $bytes[1] -le 127)
}

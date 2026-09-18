[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string] $BackendDirectory,
    [ValidateRange(1, 65535)] [int] $Port = 8000,
    [string] $BindAddress = "127.0.0.1",
    [string] $PythonExecutable
)

. (Join-Path $PSScriptRoot "operations-common.ps1")
$backend = Get-BackendDirectory $BackendDirectory
$isLoopback = $BindAddress -in @("127.0.0.1", "localhost", "::1")
if (-not $isLoopback -and -not (Test-TailscaleIPv4 $BindAddress)) {
    throw "Only loopback or an explicit Tailscale IPv4 address in 100.64.0.0/10 is allowed."
}
if (-not $isLoopback -and [string]::IsNullOrWhiteSpace($env:SUPERMARKET_LOCAL_APP_TOKEN)) {
    throw "SUPERMARKET_LOCAL_APP_TOKEN must be set before enabling a Tailscale bind."
}
if ($PSCmdlet.ShouldProcess("Supermarket Evolution backend", "Start on $BindAddress`:$Port")) {
    $python = Get-BackendPython $backend $PythonExecutable
    Push-Location $backend
    try {
        $env:SUPERMARKET_BIND_HOST = $BindAddress
        $env:SUPERMARKET_BIND_PORT = $Port
        & $python -m uvicorn app.api.main:app --host $BindAddress --port $Port
        exit $LASTEXITCODE
    }
    finally { Pop-Location }
}

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string] $FrontendDirectory,
    [string] $BackendDirectory,
    [string] $BindAddress = "127.0.0.1",
    [int] $Port = 8000,
    [switch] $SkipBuild
)

. (Join-Path $PSScriptRoot "operations-common.ps1")
if (-not $FrontendDirectory) { $FrontendDirectory = Join-Path (Get-ProjectRoot) "src\frontend" }
$backend = Get-BackendDirectory $BackendDirectory
$frontend = (Resolve-Path $FrontendDirectory).Path
if ($PSCmdlet.ShouldProcess("Supermarket Evolution local service", "Build frontend and start backend")) {
    if (-not $SkipBuild) {
        Push-Location $frontend
        try { npm run build; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
        finally { Pop-Location }
    }
    & (Join-Path $PSScriptRoot "start-backend.ps1") -BackendDirectory $backend -BindAddress $BindAddress -Port $Port
    exit $LASTEXITCODE
}

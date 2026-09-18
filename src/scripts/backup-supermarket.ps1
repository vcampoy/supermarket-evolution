[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string] $BackendDirectory,
    [string] $OutputDirectory,
    [string] $PythonExecutable
)

. (Join-Path $PSScriptRoot "operations-common.ps1")
if (-not $OutputDirectory) { $OutputDirectory = Join-Path (Get-ProjectRoot) "backups" }
$backend = Get-BackendDirectory $BackendDirectory
if ($PSCmdlet.ShouldProcess("local database, PDFs and non-secret config", "Create backup in $OutputDirectory")) {
    Activate-BackendEnvironment $backend
    $python = Get-BackendPython $backend $PythonExecutable
    Push-Location $backend
    try {
        & $python -m app.cli backup --output $OutputDirectory --config-file (Join-Path $backend "alembic.ini") --config-file (Join-Path $backend ".env.example")
        exit $LASTEXITCODE
    }
    finally { Pop-Location }
}

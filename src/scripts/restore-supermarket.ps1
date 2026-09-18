[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)] [string] $ArchivePath,
    [string] $BackendDirectory,
    [string] $DatabasePath,
    [string] $TicketsDirectory,
    [string] $ConfigDirectory,
    [string] $PythonExecutable
)

. (Join-Path $PSScriptRoot "operations-common.ps1")
$backend = Get-BackendDirectory $BackendDirectory
if (-not $DatabasePath) { $DatabasePath = Join-Path $backend "supermarket-evolution.db" }
if (-not $TicketsDirectory) { $TicketsDirectory = Join-Path (Get-ProjectRoot) "tickets" }
if ($PSCmdlet.ShouldProcess("local database and ticket archive", "Restore $ArchivePath")) {
    Write-Warning "Stop the backend before restoring. Existing files are overwritten only when their backup path matches."
    Activate-BackendEnvironment $backend
    $python = Get-BackendPython $backend $PythonExecutable
    Push-Location $backend
    try {
        $arguments = @("-m", "app.cli", "restore", (Resolve-Path $ArchivePath).Path, "--database", $DatabasePath, "--tickets", $TicketsDirectory)
        if ($ConfigDirectory) { $arguments += @("--config", $ConfigDirectory) }
        & $python @arguments
        exit $LASTEXITCODE
    }
    finally { Pop-Location }
}

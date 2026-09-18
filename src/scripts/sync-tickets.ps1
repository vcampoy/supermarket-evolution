[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string] $BackendDirectory,
    [string] $PythonExecutable,
    [string] $LogDirectory,
    [int] $MaxRetries = 3,
    [int] $RetryDelaySeconds = 30,
    [string] $MutexName = "Local\SupermarketEvolution-Sync"
)

. (Join-Path $PSScriptRoot "operations-common.ps1")
if (-not $LogDirectory) { $LogDirectory = Join-Path (Get-ProjectRoot) "logs" }
$backend = Get-BackendDirectory $BackendDirectory
$log = Get-OperationalLogPath $LogDirectory "sync-tickets.log"
$mutex = $null
$hasLock = $false

if ($MaxRetries -lt 1 -or $MaxRetries -gt 5) { throw "MaxRetries must be between 1 and 5." }
if ($RetryDelaySeconds -lt 0 -or $RetryDelaySeconds -gt 3600) { throw "RetryDelaySeconds is out of range." }
if (-not $PSCmdlet.ShouldProcess("Gmail ticket synchronization", "Run incremental sync")) { exit 0 }

try {
    $created = $false
    $mutex = [Threading.Mutex]::new($false, $MutexName, [ref] $created)
    $hasLock = $mutex.WaitOne(0)
    if (-not $hasLock) {
        Write-OperationalLog $log "sync" "skipped" "another execution is already running"
        exit 0
    }
    Write-OperationalLog $log "sync" "started"
    Rotate-OperationalLog $log
    Activate-BackendEnvironment $backend
    $python = Get-BackendPython $backend $PythonExecutable
    Push-Location $backend
    try {
        for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
            & $python -m app.cli sync --since-last *> $null
            $exitCode = $LASTEXITCODE
            if ($exitCode -eq 0) {
                Write-OperationalLog $log "sync" "succeeded" "attempt=$attempt"
                exit 0
            }
            Write-OperationalLog $log "sync" "failed" "attempt=$attempt exitCode=$exitCode"
            if ($attempt -lt $MaxRetries) { Start-Sleep -Seconds $RetryDelaySeconds }
        }
        exit 2
    }
    finally { Pop-Location }
}
finally {
    if ($hasLock -and $null -ne $mutex) { $mutex.ReleaseMutex() }
    if ($null -ne $mutex) { $mutex.Dispose() }
}

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string] $TaskName = "Supermarket Evolution - Nightly Sync",
    [string] $SyncScript,
    [datetime] $StartTime,
    [int] $RetryCount = 3,
    [int] $RetryMinutes = 15
)

. (Join-Path $PSScriptRoot "operations-common.ps1")
if (-not $SyncScript) { $SyncScript = Join-Path $PSScriptRoot "sync-tickets.ps1" }
if (-not $StartTime) { $StartTime = Get-Date -Hour 3 -Minute 0 -Second 0 }
$resolvedScript = (Resolve-Path $SyncScript).Path
if ($RetryCount -lt 0 -or $RetryCount -gt 5) { throw "RetryCount is out of range." }
if ($RetryMinutes -lt 1 -or $RetryMinutes -gt 60) { throw "RetryMinutes is out of range." }

$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$resolvedScript`""
$trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount $RetryCount `
    -RestartInterval (New-TimeSpan -Minutes $RetryMinutes)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess("scheduled task '$TaskName'", "Register daily sync at $($StartTime.ToString('HH:mm'))")) {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Incremental local Gmail ticket synchronization for Supermarket Evolution." -Force | Out-Null
    Write-Output "Scheduled task '$TaskName' installed or updated."
}

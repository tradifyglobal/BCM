$ErrorActionPreference = 'Stop'

$taskName = 'Continuity360-UAT-Tunnel'
$scriptPath = Join-Path $PSScriptRoot 'Start-UatTunnel.ps1'
$configPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'ssh_config'
if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw 'The tunnel supervisor and local ssh_config must exist before installation.'
}
Get-Command ssh.exe -ErrorAction Stop | Out-Null
Import-Module ScheduledTasks -ErrorAction Stop
$powerShellPath = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$arguments = '-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -File "{0}"' -f $scriptPath
$existing = Get-ScheduledTask | Where-Object { $_.TaskName -eq $taskName -and $_.TaskPath -eq '\' }
if ($existing) {
    if ($existing.Actions.Count -ne 1 -or $existing.Actions[0].Execute -ne $powerShellPath -or
        $existing.Actions[0].Arguments -ne $arguments) {
        throw "Task $taskName already exists with a different action; it was not changed."
    }
    if ($existing.State -eq 'Running') {
        throw "Task $taskName is already running. Stop it explicitly before reinstalling."
    }
}
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $powerShellPath -Argument $arguments `
    -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
# Self-heal: re-check every 15 minutes so a killed supervisor restarts without a new sign-in.
# MultipleInstances IgnoreNew makes this a no-op while the tunnel is already running.
$repeatTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger, $repeatTrigger -Principal $principal `
    -Settings $settings -Description 'User-scoped, localhost-only UAT SSH tunnel with automatic reconnect.' `
    -Force | Out-Null
Write-Output "Installed $taskName. Start with: Start-ScheduledTask -TaskName $taskName"

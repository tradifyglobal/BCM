$ErrorActionPreference = 'Stop'

$configPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'ssh_config'
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "SSH configuration not found: $configPath"
}
$sshPath = (Get-Command ssh.exe -ErrorAction Stop).Source
$logDirectory = Join-Path $env:LOCALAPPDATA 'Continuity360'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$logPath = Join-Path $logDirectory 'uat-tunnel.log'

function Write-TunnelLog([string] $Message) {
    if ((Test-Path -LiteralPath $logPath) -and (Get-Item -LiteralPath $logPath).Length -gt 1MB) {
        Move-Item -LiteralPath $logPath -Destination "$logPath.1" -Force
    }
    Add-Content -LiteralPath $logPath -Value ("{0:o} {1}" -f (Get-Date), $Message) -Encoding UTF8
}

Write-TunnelLog 'Starting UAT tunnel supervisor on 127.0.0.1:18080.'
while ($true) {
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $sshPath
    $startInfo.Arguments = (
        '-F "{0}" -N -T -o BatchMode=yes -o ExitOnForwardFailure=yes ' +
        '-o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ConnectTimeout=10 ' +
        '-L 127.0.0.1:18080:127.0.0.1:18080 continuity360-uat'
    ) -f $configPath
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.RedirectStandardOutput = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    $started = $false
    try {
        $started = $process.Start()
        if (-not $started) {
            throw 'OpenSSH did not start.'
        }
        Write-TunnelLog ("OpenSSH started, PID {0}." -f $process.Id)
        $stderr = $process.StandardError.ReadToEndAsync()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $process.WaitForExit()
        $errorText = $stderr.GetAwaiter().GetResult()
        $outputText = $stdout.GetAwaiter().GetResult()
        Write-TunnelLog ("OpenSSH exited with code {0}. {1} {2}" -f $process.ExitCode,
            $errorText.Trim(), $outputText.Trim())
    } finally {
        if ($started -and -not $process.HasExited) {
            $process.Kill()
            $process.WaitForExit()
        }
        $process.Dispose()
    }
    Write-TunnelLog 'Retrying in 5 seconds.'
    Start-Sleep -Seconds 5
}

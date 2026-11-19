param([string]$Pi = 'pi@100.68.26.99', [int]$LocalPort = 8765, [int]$RemotePort = 8765)
$ErrorActionPreference = 'Stop'
if ($LocalPort -lt 1 -or $LocalPort -gt 65535 -or $RemotePort -lt 1 -or $RemotePort -gt 65535) { throw 'Ports must be between 1 and 65535.' }
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) { throw 'OpenSSH is unavailable. Install the Windows OpenSSH client.' }
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $LocalPort)
try { $listener.Start() } catch { throw "Local port $LocalPort is already in use. Choose another with -LocalPort." } finally { $listener.Stop() }
$sshArgs = @('-N', '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=8', '-L', "127.0.0.1:${LocalPort}:127.0.0.1:${RemotePort}", $Pi)
$process = $null
try {
    $process = Start-Process -FilePath 'ssh.exe' -ArgumentList $sshArgs -PassThru -WindowStyle Hidden
    $ready = $false
    for ($i = 0; $i -lt 100; $i++) {
        if ($process.HasExited) { throw 'SSH could not connect or set up the tunnel. Check Tailscale, SSH keys, and the Pi address.' }
        $client = [System.Net.Sockets.TcpClient]::new()
        try { $client.Connect('127.0.0.1', $LocalPort); $ready = $true; break } catch {} finally { $client.Dispose() }
        Start-Sleep -Milliseconds 100
    }
    if (-not $ready) { throw 'SSH tunnel timed out. Check Tailscale and the Pi connection.' }
    $url = "http://127.0.0.1:$LocalPort/"
    try { $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10; if ($response.StatusCode -ne 200) { throw 'Unexpected response' } }
    catch { throw 'The SSH tunnel is open, but the Pi dashboard is unavailable. Start buoy-dashboard on the Pi.' }
    Start-Process $url
    Write-Host "Dashboard opened at $url. Keep this window open; press Enter to close the tunnel."
    Read-Host | Out-Null
} finally {
    if ($null -ne $process -and -not $process.HasExited) { Stop-Process -Id $process.Id }
}

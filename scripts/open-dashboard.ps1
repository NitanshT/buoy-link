param([Parameter(Mandatory=$true, Position=0)][string]$Pi, [int]$LocalPort = 8765, [int]$RemotePort = 8765)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class TunnelJob {
    [StructLayout(LayoutKind.Sequential)] public struct BasicLimits {
        public long PerProcessUserTimeLimit, PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }
    [StructLayout(LayoutKind.Sequential)] public struct IoCounters {
        public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
        public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
    }
    [StructLayout(LayoutKind.Sequential)] public struct ExtendedLimits {
        public BasicLimits BasicLimitInformation;
        public IoCounters IoInfo;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern IntPtr CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool SetInformationJobObject(IntPtr job, int type, ref ExtendedLimits info, uint length);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool CloseHandle(IntPtr handle);
    public static IntPtr Create() {
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) throw new System.ComponentModel.Win32Exception();
        var limits = new ExtendedLimits();
        limits.BasicLimitInformation.LimitFlags = 0x2000;
        if (!SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf(typeof(ExtendedLimits)))) {
            CloseHandle(job); throw new System.ComponentModel.Win32Exception();
        }
        return job;
    }
}
'@
if ($LocalPort -lt 1 -or $LocalPort -gt 65535 -or $RemotePort -lt 1 -or $RemotePort -gt 65535) { throw 'Ports must be between 1 and 65535.' }
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) { throw 'OpenSSH is unavailable. Install the Windows OpenSSH client.' }
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $LocalPort)
try { $listener.Start() } catch { throw "Local port $LocalPort is already in use. Choose another with -LocalPort." } finally { $listener.Stop() }
$sshArgs = @('-N', '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=8', '-L', "127.0.0.1:${LocalPort}:127.0.0.1:${RemotePort}", $Pi)
$process = $null
$job = [IntPtr]::Zero
try {
    $job = [TunnelJob]::Create()
    $process = Start-Process -FilePath 'ssh.exe' -ArgumentList $sshArgs -PassThru -WindowStyle Hidden
    if (-not [TunnelJob]::AssignProcessToJobObject($job, $process.Handle)) { throw 'Could not attach SSH to the cleanup job.' }
    $ready = $false
    for ($i = 0; $i -lt 100; $i++) {
        if ($process.HasExited) { throw 'SSH could not connect or set up the tunnel. Check the network, host key, SSH keys, and Pi address.' }
        $client = [System.Net.Sockets.TcpClient]::new()
        try { $client.Connect('127.0.0.1', $LocalPort); $ready = $true; break } catch {} finally { $client.Dispose() }
        Start-Sleep -Milliseconds 100
    }
    if (-not $ready) { throw 'SSH tunnel timed out. Check the network and Pi connection.' }
    $url = "http://127.0.0.1:$LocalPort/"
    try { $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10; if ($response.StatusCode -ne 200) { throw 'Unexpected response' } }
    catch { throw 'The SSH tunnel is open, but the Pi dashboard is unavailable. Start buoy-dashboard on the Pi.' }
    Start-Process $url
    Write-Host "Dashboard opened at $url. Keep this window open; press Enter to close the tunnel."
    Read-Host | Out-Null
} finally {
    try { if ($null -ne $process -and -not $process.HasExited) { Stop-Process -Id $process.Id } }
    finally { if ($job -ne [IntPtr]::Zero) { [void][TunnelJob]::CloseHandle($job) } }
}

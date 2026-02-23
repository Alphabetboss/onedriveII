param(
  [string]$PiHost = "raspberrypi.local",  # or 192.168.x.x
  [string]$PiUser = "Alpha",              # your Pi username
  [switch]$TunnelApp,                     # add -TunnelApp to forward the web app
  [int]$LocalPort = 5051,                 # local browser port
  [int]$RemotePort = 5051                 # app port on the Pi
)

# Ensure OpenSSH client is available
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
  Write-Error "OpenSSH client not found. Windows: Settings > Apps > Optional Features > Add 'OpenSSH Client'."
  exit 1
}

Write-Host "Checking SSH on $PiHost:22 ..."
$sshReachable = (Test-NetConnection $PiHost -Port 22 -InformationLevel Quiet)
if (-not $sshReachable) {
  Write-Warning "SSH on $PiHost:22 didn't respond. If you know the Pi's IP, run with: -PiHost 192.168.x.x"
  Write-Warning "Make sure SSH is enabled on the Pi: sudo raspi-config → Interface Options → SSH → Enable"
}

# Build SSH arguments
$sshArgs = @()
if ($TunnelApp) {
  $sshArgs += "-L"
  $sshArgs += "$LocalPort:127.0.0.1:$RemotePort"
  Write-Host "When connected, open http://127.0.0.1:$LocalPort in your browser to reach the app."
}

$target = "$PiUser@$PiHost"
Write-Host "Connecting as $PiUser to $PiHost ..."
ssh @sshArgs $target

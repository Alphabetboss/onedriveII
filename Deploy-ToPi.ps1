# PowerShell
# Deploy-ToPi.ps1 — ship Ingenious Irrigation to Raspberry Pi + autostart via systemd

$ErrorActionPreference = "Stop"

### ====== EDIT THESE 3 LINES ====== ###
$PiHost = "192.168.1.42"     # <-- your Pi's IP address
$PiUser = "pi"               # <-- your Pi username
$PiDir  = "/home/pi/ingenious"  # install location on the Pi
### ================================= ###

# Optional: if you use SSH key auth, leave $PiPass empty. If you need password prompts, you'll be asked interactively.
$PiPass = "" # leave empty for key-based auth; press Enter when ssh/scp prompts

# --- Sanity checks ---
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) { throw "OpenSSH not found. On Windows 10/11, enable 'OpenSSH Client' feature." }
if (-not (Get-Command scp -ErrorAction SilentlyContinue)) { throw "SCP not found. On Windows 10/11, enable 'OpenSSH Client' feature." }

# --- Paths ---
$ProjectRoot = Get-Location
$Stage = Join-Path $env:TEMP "ii_stage_$([Guid]::NewGuid().ToString('N'))"

Write-Host "Staging from $ProjectRoot to $Stage ..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

# --- Copy project -> staging, excluding heavy/irrelevant folders ---
# Keep: app.py, *.py modules, templates/, static/, data/, .env (optional), etc.
# Exclude: .venv, __pycache__, logs, .git, runs, cache, dataset, models (if huge), .ruff_cache, .vscode
robocopy $ProjectRoot $Stage /E /NFL /NDL /NJH /NJS /NC /NS `
  /XD ".venv" "__pycache__" ".git" "runs" "logs" "cache" ".ruff_cache" ".vscode" "dataset" "ai\weights" "models\checkpoints" `
  /XF "*.bak_*" "*.old" "*.tmp" > $null

# Ensure minimal runtime files exist
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "data"), (Join-Path $Stage "static"), (Join-Path $Stage "templates") | Out-Null
if (-not (Test-Path (Join-Path $Stage "static\favicon.ico"))) { [IO.File]::WriteAllBytes((Join-Path $Stage "static\favicon.ico"), [byte[]]@()) }
if (-not (Test-Path (Join-Path $Stage "static\audio"))) { New-Item -ItemType Directory -Force -Path (Join-Path $Stage "static\audio") | Out-Null }
if (-not (Test-Path (Join-Path $Stage "static\audio\startup.mp3"))) { [IO.File]::WriteAllBytes((Join-Path $Stage "static\audio\startup.mp3"), [byte[]]@()) }

# --- Push code to the Pi ---
Write-Host "Creating target dir $PiDir on Pi ..." -ForegroundColor Cyan
ssh "$PiUser@$PiHost" "mkdir -p $PiDir"

Write-Host "Copying project to Pi (this may take a minute)..." -ForegroundColor Cyan
scp -r "$Stage/*" "$PiUser@$PiHost:$PiDir/"

# --- Write requirements + service file on the Pi (idempotent) ---
$req = @'
flask
requests
twilio
RPi.GPIO; platform_system == "Linux"
'@

$service = @"
[Unit]
Description=Ingenious Irrigation (Astra) Flask Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$PiUser
WorkingDirectory=$PiDir
Environment=PYTHONUNBUFFERED=1
ExecStart=$PiDir/.venv/bin/python $PiDir/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"@

# Upload requirements.txt and service via SSH here-strings
Write-Host "Writing requirements.txt and systemd unit..." -ForegroundColor Cyan
ssh "$PiUser@$PiHost" "bash -lc 'cat > $PiDir/requirements.txt <<EOF
$req
EOF
sudo bash -lc ""cat > /etc/systemd/system/ingenious.service <<'UNIT'
$service
UNIT
"""  # end of ssh command

# --- Create venv & install packages on the Pi ---
Write-Host "Creating venv + installing Python packages..." -ForegroundColor Cyan
ssh "$PiUser@$PiHost" "bash -lc 'sudo apt-get update -y && sudo apt-get install -y python3-venv python3-pip && cd $PiDir && python3 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt'"

# --- Enable firewall (optional) + allow 5051 ---
Write-Host "Ensuring port 5051 reachable (ufw optional)..." -ForegroundColor Cyan
ssh "$PiUser@$PiHost" "bash -lc 'if command -v ufw >/dev/null 2>&1; then sudo ufw allow 5051/tcp || true; fi'"

# --- Enable + start the service ---
Write-Host "Enabling and starting ingenious.service ..." -ForegroundColor Cyan
ssh "$PiUser@$PiHost" "bash -lc 'sudo systemctl daemon-reload && sudo systemctl enable ingenious.service && sudo systemctl restart ingenious.service'"

# --- Status + tail logs ---
Write-Host "`nService status:" -ForegroundColor Yellow
ssh "$PiUser@$PiHost" "bash -lc 'systemctl --no-pager status ingenious.service | sed -n \"1,25p\"'"

Write-Host "`nRecent logs (Ctrl+C to stop tail):" -ForegroundColor Yellow
ssh "$PiUser@$PiHost" "bash -lc 'journalctl -u ingenious.service -n 50 -f --output=cat'"

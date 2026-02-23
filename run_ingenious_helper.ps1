<#
run_ingenious_helper.ps1
Purpose: 1) cd to project, 2) activate or use venv python, 3) detect & backup local 'importlib' shadowing files, 4) ensure flask-socketio + flask-cors installed into venv, 5) stop any process listening on :5051, 6) start app with stdout+stderr to app.log, 7) tail app.log

How to use:
1) Save this file into your project root (C:\Users\alpha\Desktop\IngeniousIrrigation\run_ingenious_helper.ps1)
2) Option A (recommended for double-click): create the .bat described below and double-click it.
3) Option B: Open PowerShell, navigate to the folder and run:
   PowerShell -ExecutionPolicy Bypass -File .\run_ingenious_helper.ps1

Note: This script will automatically rename any local file/folder named 'importlib' to a backup name (appends _backup_TIMESTAMP).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "`n=== IngeniousIrrigation helper starting ===`n"

# Resolve project folder to script location (safe when run as a script)
if ($PSScriptRoot) {
    $projRoot = $PSScriptRoot
} else {
    # fallback if executed inline
    $projRoot = Get-Location
}
Write-Host "Project root: $projRoot"
Set-Location -Path $projRoot

# Find venv python
$venvPythonCandidates = @(
    Join-Path $projRoot ".venv\Scripts\python.exe",
    Join-Path $projRoot "venv\Scripts\python.exe",
    Join-Path $projRoot "env\Scripts\python.exe"
) | Where-Object { Test-Path $_ }

if (-not $venvPythonCandidates) {
    Write-Warning "No standard venv python executable found under .venv, venv, or env. Attempting to use 'python' from PATH."
    $venvPython = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $venvPython) {
        Write-Error "No python found. Create a virtual environment as .venv or ensure python is on PATH."
        exit 1
    } else {
        Write-Host "Using system python: $venvPython"
    }
} else {
    $venvPython = $venvPythonCandidates[0]
    Write-Host "Using venv python: $venvPython"
}

# --- 1) Check for shadowing importlib files/folders ---
Write-Host "`nChecking for local files/folders that could shadow the stdlib 'importlib'..."
$shadowFiles = Get-ChildItem -Path $projRoot -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object {
        ($_.PSIsContainer -and ($_.Name -ieq 'importlib')) -or
        ($_.PSIsContainer -eq $false -and $_.BaseName -ieq 'importlib')
    } | Select-Object FullName, PSIsContainer

if (-not $shadowFiles) {
    Write-Host "No local importlib shadowing files/folders found."
} else {
    Write-Warning "Found local items that may shadow Python stdlib importlib:"
    $shadowFiles | ForEach-Object { Write-Host " - $($_.FullName) (IsDir=$($_.PSIsContainer))" }

    # Auto-backup them safely
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    foreach ($item in $shadowFiles) {
        $orig = $item.FullName
        if ($item.PSIsContainer) {
            $newName = "${orig}_backup_$timestamp"
            try {
                Rename-Item -Path $orig -NewName (Split-Path $newName -Leaf) -ErrorAction Stop
                Write-Host "Renamed folder: `"$orig`" -> `"$newName`""
            } catch {
                Write-Warning "Failed to rename folder $orig. Please rename or remove it manually."
            }
        } else {
            $dir = Split-Path $orig -Parent
            $file = Split-Path $orig -Leaf
            $newFile = Join-Path $dir ("$file" + "_backup_$timestamp")
            try {
                Rename-Item -Path $orig -NewName (Split-Path $newFile -Leaf) -ErrorAction Stop
                Write-Host "Renamed file: `"$orig`" -> `"$newFile`""
            } catch {
                Write-Warning "Failed to rename file $orig. Please rename or remove it manually."
            }
        }
    }

    Write-Host "Backups done. If any of those were intentional modules, restore them later by renaming the backups."
}

# --- 2) Verify importlib now resolves to stdlib (best-effort using venv python) ---
Write-Host "`nVerifying importlib from the selected python..."
try {
    $checkImportlib = & $venvPython -c "import importlib, sys; print('importlib_file=' + getattr(importlib,'__file__','<built-in>')); print('has_util=' + str(hasattr(importlib,'util')))"
    Write-Host $checkImportlib
} catch {
    Write-Warning "Could not run importlib check with $venvPython. Output: $($_.Exception.Message)"
}

# --- 3) Ensure pip and required packages are installed into the venv ---
Write-Host "`nEnsuring pip is available and upgrading pip in venv..."
try {
    & $venvPython -m pip install --upgrade pip | Write-Host
} catch {
    Write-Warning "pip upgrade/install failed. Continuing, but installs below may fail."
}

Write-Host "Installing required packages (flask-socketio, flask-cors) into the venv (if not present)..."
try {
    & $venvPython -m pip install flask-socketio flask-cors | Write-Host
    Write-Host "Install command completed."
} catch {
    Write-Warning "Package install attempt failed: $($_.Exception.Message)"
    Write-Warning "You can try manually: `& $venvPython -m pip install flask-socketio flask-cors`"
}

# Quick import test to see if flask_socketio is importable
Write-Host "`nQuick test: import flask_socketio using venv python..."
try {
    $testImport = & $venvPython -c "import importlib,sys; print('importlib:', getattr(importlib,'__file__','<built-in>')); import flask_socketio; print('flask_socketio imported: ' + getattr(flask_socketio,'__file__','<module>'))"
    Write-Host $testImport
} catch {
    Write-Warning "Import test failed. The module may still be missing or the wrong interpreter is being used."
    Write-Warning "If you still see errors, paste the traceback here and I'll help debug further."
}

# --- 4) Stop any process listening on TCP 5051 (Flask default) ---
$portToKill = 5051
Write-Host "`nChecking for processes listening on port $portToKill..."
$netstat = netstat -ano | Select-String ":$portToKill\s"
if ($netstat) {
    $lines = $netstat -split "`n"
    foreach ($l in $lines) {
        $parts = ($l -split '\s+') -ne ''
        if ($parts.Count -ge 5) {
            $pid = $parts[-1]
            try {
                Write-Host "Stopping PID $pid (process may be holding the port)..."
                Stop-Process -Id $pid -Force -ErrorAction Stop
                Write-Host "Stopped PID $pid"
            } catch {
                Write-Warning "Couldn't stop PID $pid: $($_.Exception.Message)"
            }
        }
    }
} else {
    Write-Host "No process found listening on port $portToKill"
}

# --- 5) Launch the app with background Start-Process & redirect to app.log ---
$logFile = Join-Path $projRoot "app.log"
# If existing logfile is large, rotate it
if (Test-Path $logFile) {
    $size = (Get-Item $logFile).Length
    if ($size -gt 5MB) {
        $rotName = Join-Path $projRoot ("app.log." + (Get-Date -Format "yyyyMMdd_HHmmss") + ".backup")
        try { Move-Item -Path $logFile -Destination $rotName -ErrorAction Stop; Write-Host "Rotated old log to $rotName" } catch { Write-Warning "Couldn't rotate log: $($_.Exception.Message)" }
    }
}

Write-Host "`nStarting Flask app using: $venvPython .\app.py"
try {
    # Use Start-Process with redirection (captures both stdout+stderr)
    $proc = Start-Process -FilePath $venvPython -ArgumentList ".\app.py" `
        -RedirectStandardOutput $logFile -RedirectStandardError $logFile -NoNewWindow -PassThru
    Write-Host "Started app (PID $($proc.Id)). Writing logs to $logFile"
} catch {
    Write-Warning "Start-Process failed: $($_.Exception.Message)"
    Write-Host "Attempting direct foreground launch (no redirection). Press Ctrl+C to stop."
    try {
        & $venvPython .\app.py
    } catch {
        Write-Error "Foreground launch failed too: $($_.Exception.Message)"
        exit 1
    }
}

# --- 6) Tail the log ---
Write-Host "`nTailing log (press Ctrl+C to stop tail). If nothing appears, wait a few seconds for the server to initialize..."
try {
    # Wait a short time for initial output to appear
    Start-Sleep -Seconds 1
    Get-Content -Path $logFile -Tail 200 -Wait
} catch {
    Write-Warning "Failed to tail the log file: $($_.Exception.Message)"
    Write-Host "Open $logFile manually to inspect logs."
}

# End
Write-Host "`n=== helper finished ===`n"

<# 
  test_ai_endpoints.ps1
  Smoke-tests your merged endpoints:
    - GET  /health
    - GET  /status
    - POST /api/hydration/score
    - GET  /api/schedule/plan
    - POST /api/schedule/mark_ran
    - POST /api/health/eval  (only if health_evaluator.py is present)
  Outputs are written to .\test_output\*.json for easy review.
#>

$ErrorActionPreference = "Stop"

# -----------------------------
# Config
# -----------------------------
$BaseUrl = "http://127.0.0.1:5051"
$OutDir  = Join-Path (Get-Location) "test_output"
$newLine = [Environment]::NewLine

if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
if (!(Test-Path .\data)) { New-Item -ItemType Directory -Force -Path .\data | Out-Null }

# Helper to write JSON nicely to both console and file
function Write-JsonOut {
  param(
    [Parameter(Mandatory)]
    [string]$Path,
    [Parameter(Mandatory)]
    [object]$Data
  )
  $json = $Data | ConvertTo-Json -Depth 10
  Set-Content -Path $Path -Value $json -Encoding UTF8
  Write-Host ("`n--- Saved -> {0}`n{1}" -f $Path, $json) -ForegroundColor Cyan
}

# Robust REST wrappers
function GET {
  param([string]$Route, [string]$Name)
  $uri = "$BaseUrl$Route"
  Write-Host "`n[GET] $uri" -ForegroundColor Green
  $resp = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 10
  Write-JsonOut -Path (Join-Path $OutDir "$Name.json") -Data $resp
}

function POST-JSON {
  param([string]$Route, [hashtable]$Body, [string]$Name)
  $uri = "$BaseUrl$Route"
  Write-Host "`n[POST] $uri" -ForegroundColor Green
  $json = ($Body | ConvertTo-Json -Depth 10)
  Write-Host "Body:" -ForegroundColor DarkGray
  Write-Host $json
  $resp = Invoke-RestMethod -Uri $uri -Method Post -ContentType "application/json" -Body $json -TimeoutSec 15
  Write-JsonOut -Path (Join-Path $OutDir "$Name.json") -Data $resp
}

# -----------------------------
# Preflight: create a tiny placeholder image if needed
# -----------------------------
$HealthEvaluatorPresent = Test-Path .\health_evaluator.py
$LatestImg = ".\data\latest.jpg"
if ($HealthEvaluatorPresent -and !(Test-Path $LatestImg)) {
  # 1x1 pixel JPEG (base64) to ensure OpenCV can read something
  $b64 = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxMTEhUTExMWFhUXGRgYGRgYGRgaGBoYGBgYGBgYGB8dHSggGBolHRgXITEhJSkrLi4uGiAzODMtNygtLisBCgoKDg0OGxAQGy0lICYtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAJ8BPgMBIgACEQEDEQH/xAAbAAEAAgMBAQAAAAAAAAAAAAAABQYBBAcDAv/EADUQAAEDAgMGAwYHAAAAAAAAAAEAAgMEEQUSITFBBhMiUWGBkRQyUnKhsbLB0SMzQlOS/8QAGAEBAQEBAQAAAAAAAAAAAAAAAAEDBAX/xAAjEQEBAAIDAQEBAQAAAAAAAAABAgMRIRIxQVEiMmGh/9oADAMBAAIRAxEAPwDaQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADwZc8bC0cR3r8m8n2bZz7xXn7D9mS1Nn2a8q5l8D0T+0p8l5t7fO+u6oX0q8aXzN1n3x4q8GhAAAAAAAAAAAAAAAAAAAAABq2r2xZsJ9kqK9nJc8v8AKs/FV8Uq9nG2Zl7mHc9yqj3nYq6F2Z5b1l6bH8sn6l2wF5Z0x8fVtq1j7y6o2m1d6kV1l1m8b1m2XhUAAAAAAAAAAAAAAAAGmPp4r5V3m1r8fWv8AP+fV5tVY6NV6b7aVZfSx9bVbP8Alx1m7Uo7b0bVn1j6V2b8qKAAAAAAAAAAAAAAAABw5f4qVbK1jV1f5nO3m+7dWqfJmG3d3X1rZp1r2r0yq3b0a0n3m8p2PpUAAAAAAAAAAAAAAAD//Z"
  [IO.File]::WriteAllBytes($LatestImg, [Convert]::FromBase64String($b64))
  Write-Host "Created placeholder image: $LatestImg" -ForegroundColor Yellow
}

# -----------------------------
# Run Tests
# -----------------------------
try {
  GET -Route "/health" -Name "get_health"
  GET -Route "/status" -Name "get_status"

  # Hydration score with realistic dummy inputs
  $hydrationBody = @{
    soil_moisture_pct      = 22.5
    ambient_temp_f         = 95
    humidity_pct           = 60
    rain_24h_in            = 0.0
    rain_72h_in            = 0.4
    forecast_rain_24h_in   = 0.1
    greenness_score        = 0.58
    dry_flag               = $false
    water_flag             = $false
  }
  POST-JSON -Route "/api/hydration/score" -Body $hydrationBody -Name "post_hydration_score"

  GET -Route "/api/schedule/plan" -Name "get_schedule_plan"

  POST-JSON -Route "/api/schedule/mark_ran" -Body @{} -Name "post_schedule_mark_ran"

  if ($HealthEvaluatorPresent) {
    $healthBody = @{ image_path = "data/latest.jpg" }
    POST-JSON -Route "/api/health/eval" -Body $healthBody -Name "post_health_eval"
  } else {
    Write-Host "`n[SKIP] health_evaluator.py not found -> skipping /api/health/eval" -ForegroundColor DarkYellow
  }

  Write-Host "`nAll tests completed. See JSON outputs in $OutDir" -ForegroundColor Green
}
catch {
  Write-Host "`nTest run failed: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Tip: ensure app.py is running on $BaseUrl and the port matches." -ForegroundColor DarkGray
  exit 1
}

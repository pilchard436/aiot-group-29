param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Directory,
    [Parameter(Position = 1)]
    [string]$Port = "COM3"
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$sourceDirectories = @(".", $Directory, "lib") | Select-Object -Unique

foreach ($directory in $sourceDirectories) {
    $sourcePath = Join-Path $repoRoot $directory

    if (-not (Test-Path $sourcePath -PathType Container)) {
        Write-Warning "Skipping missing directory: $directory"
        continue
    }

    Push-Location $sourcePath
    try {
        Write-Host "Uploading Python files from $directory..."
        & mpfshell -nc "open $Port; mput .*\.py"
        if ($LASTEXITCODE -ne 0) {
            throw "mpfshell failed while uploading files from $directory."
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host "Upload complete."

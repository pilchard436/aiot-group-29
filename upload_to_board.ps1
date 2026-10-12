param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Directory,
    [Parameter(Position = 1)]
    [string]$Port = "COM3",
    [string]$File,
    [string]$RemoteFile
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot

if ($File) {
    if ([System.IO.Path]::GetFileName($File) -ne $File) {
        throw "File must be a file name within the selected directory."
    }
    if (-not $RemoteFile) {
        $RemoteFile = $File
    }
    if ([System.IO.Path]::GetFileName($RemoteFile) -ne $RemoteFile) {
        throw "RemoteFile must be a file name."
    }

    $sourcePath = Join-Path (Join-Path $repoRoot $Directory) $File
    if (-not (Test-Path $sourcePath -PathType Leaf)) {
        throw "File not found: $sourcePath"
    }

    Push-Location (Split-Path $sourcePath -Parent)
    try {
        Write-Host "Uploading $File from $Directory as $RemoteFile..."
        & mpfshell -nc "open $Port; put `"$File`" `"$RemoteFile`""
        if ($LASTEXITCODE -ne 0) {
            throw "mpfshell failed while uploading $File as $RemoteFile."
        }
    }
    finally {
        Pop-Location
    }

    Write-Host "Upload complete."
    return
}

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

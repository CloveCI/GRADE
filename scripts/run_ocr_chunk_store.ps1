param(
    [string]$Pdf = "DocScanner 3 Apr 2026 12-56*.pdf",
    [string]$Output = "extraction.json",
    [string]$Query = "algorithm steps",
    [int]$TopK = 3,
    [switch]$FullPage,
    [switch]$NoQuery
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$env:PYTHONPATH = "src"

$ArgsList = @(
    "scripts\show_grade_workflow.py",
    $Pdf,
    "-o",
    $Output
)

if ($FullPage) {
    $ArgsList += "--full-page"
}

if (-not $NoQuery -and $Query.Trim()) {
    $ArgsList += "--query"
    $ArgsList += $Query
    $ArgsList += "--top-k"
    $ArgsList += [string]$TopK
}

python @ArgsList

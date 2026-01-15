$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$defaultOut = Join-Path $scriptDir "output"

$outDir = Read-Host "Output folder (default: $defaultOut)"
if ([string]::IsNullOrWhiteSpace($outDir)) {
    $outDir = $defaultOut
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

docker build -t parampara-poster $scriptDir
docker run -it --rm -v "${scriptDir}:/app" -v "${outDir}:/out" parampara-poster

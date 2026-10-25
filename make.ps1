# Équivalent Windows du Makefile : .\make.ps1 dev | migrate | init | test | lint | format | prod
# Premier admin (base vide) : .\make.ps1 init -Email prenom@digitalia-ltd.com -Name "Prénom Nom"
param([Parameter(Mandatory = $true)][ValidateSet("dev", "migrate", "init", "test", "lint", "format", "prod")][string]$Target,
      [string]$Email, [string]$Name)
function Run([string]$cmd) { Write-Host "> $cmd" -ForegroundColor Cyan; Invoke-Expression $cmd; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
switch ($Target) {
  "dev"     { Run "docker compose up --build" }
  "migrate" { Run "docker compose run --rm backend python manage.py migrate" }
  "init"    { if (-not $Email -or -not $Name) { Write-Host "Usage : .\make.ps1 init -Email ... -Name ""Prénom Nom""" -ForegroundColor Yellow; exit 1 }
              Run "docker compose run --rm backend python manage.py init_orbit --email ""$Email"" --name ""$Name""" }
  "test"    { Run "docker compose run --rm backend pytest"; Run "docker compose run --rm frontend sh -c 'npm install --no-audit --no-fund && npm test -- --run'" }
  "lint"    { Run "docker compose run --rm backend sh -c 'ruff check . && mypy .'"; Run "docker compose run --rm frontend sh -c 'npm run lint -- --max-warnings 0 && npm run format:check && npm run typecheck'" }
  "format"  { Run "docker compose run --rm backend ruff check . --fix"; Run "docker compose run --rm frontend npm run format" }
  "prod"    { Run "docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build" }
}

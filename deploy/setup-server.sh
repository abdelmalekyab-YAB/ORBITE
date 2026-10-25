#!/usr/bin/env bash
# Installe Orbit sur un serveur Ubuntu 22.04/24.04 neuf (OVH, Hetzner...). À lancer en root :
#   curl -fsSL https://raw.githubusercontent.com/abdelmalekyab-YAB/ORBITE/main/deploy/setup-server.sh | bash -s -- orbit.mondomaine.fr admin@mondomaine.fr "Prénom Nom"
# Le DNS du domaine doit déjà pointer vers l'adresse IP du serveur (enregistrement A).
set -euo pipefail

DOMAIN="${1:?Usage: setup-server.sh DOMAINE EMAIL_ADMIN NOM_ADMIN}"
ADMIN_EMAIL="${2:?E-mail du premier administrateur manquant}"
ADMIN_NAME="${3:?Nom du premier administrateur manquant}"
REPO="${ORBIT_REPO:-https://github.com/abdelmalekyab-YAB/ORBITE.git}"
BRANCH="${ORBIT_BRANCH:-main}"
DIR=/opt/orbit
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"

echo "==> Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi

echo "==> Pare-feu (SSH, HTTP, HTTPS)"
if command -v ufw >/dev/null; then
  ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
fi

echo "==> Code"
if [ ! -d "$DIR/.git" ]; then git clone --branch "$BRANCH" "$REPO" "$DIR"; fi
cd "$DIR" && git pull --ff-only

echo "==> Configuration (.env.prod, créé une seule fois)"
if [ ! -f .env.prod ]; then
  secret() { tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"; }
  DB_PASSWORD="$(secret 32)"
  sed -e "s|orbit.exemple.com|$DOMAIN|g" \
      -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(secret 60)|" \
      -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$DB_PASSWORD|" \
      -e "s|MOT_DE_PASSE|$DB_PASSWORD|" \
      -e "s|orbit@exemple.com|orbit@$DOMAIN|" \
      .env.prod.example > .env.prod
  chmod 600 .env.prod
  echo "   .env.prod créé. Renseignez ensuite l'envoi d'e-mails (EMAIL_*) puis relancez : cd $DIR && $COMPOSE up -d"
fi

echo "==> Démarrage (le premier lancement prend quelques minutes)"
$COMPOSE up -d --build

echo "==> Premier administrateur"
for _ in $(seq 1 30); do
  if $COMPOSE exec -T backend python manage.py check >/dev/null 2>&1; then break; fi
  sleep 5
done
$COMPOSE exec -T backend python manage.py init_orbit --email "$ADMIN_EMAIL" --name "$ADMIN_NAME" || \
  echo "   (déjà initialisé, ou relancez : $COMPOSE exec backend python manage.py init_orbit --email ... --name ...)"

echo
echo "Orbit est en ligne sur https://$DOMAIN"
echo "Le lien pour choisir le mot de passe administrateur est affiché ci-dessus (et envoyé par e-mail une fois les EMAIL_* renseignés)."

#!/usr/bin/env bash
# Mise à jour de Precis FC sur l'hébergement cPanel (LWS).
# À lancer dans le Terminal cPanel :
#   VENV=$HOME/virtualenv/precisfc/3.13 bash ~/precisfc/deploy/scripts/deploy_cpanel.sh
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/precisfc}"
VENV="${VENV:?Indiquer le virtualenv cPanel, ex. VENV=\$HOME/virtualenv/precisfc/3.13}"

cd "$APP_DIR"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
export DJANGO_SETTINGS_MODULE=config.settings.prod

PREVIOUS_COMMIT="$(git rev-parse HEAD)"
echo "Version actuelle : $PREVIOUS_COMMIT (à utiliser en cas de retour arrière)"

git pull --ff-only
pip install --quiet -r requirements/cpanel.txt

# Contrôles bloquants AVANT de toucher à la base (jeu de caractères, InnoDB, sécurité).
python manage.py check --deploy --database default --fail-level ERROR

python manage.py migrate --noinput
python manage.py createcachetable
python manage.py collectstatic --noinput

mkdir -p tmp
touch tmp/restart.txt   # redémarre l'application Passenger

echo "Déploiement terminé : $(git rev-parse --short HEAD)"

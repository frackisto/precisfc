# Guide de déploiement sur l'hébergement cPanel (LWS)

> Guide utilisé pour le **déploiement de test** (étape 3), puis pour la mise en production (étape 16).
> Remplacer partout :
> - `<compte>` : votre identifiant cPanel ;
> - `<domaine>` : le domaine ou sous-domaine du site ;
> - `<racine-web>` : la « racine du document » de ce domaine, visible dans cPanel → **Domaines** ou avec `uapi DomainInfo single_domain_data domain=<domaine> | grep documentroot` (ex. `/home/<compte>/public_html` pour le domaine principal). Ce n'est **jamais** le dossier du projet `~/precisfc` ;
> - `<identifiant-github>` : votre identifiant GitHub.

**Conseil :** pour le test, utilisez un **sous-domaine dédié** (ex. `beta.<domaine>`), créé dans cPanel → **Domaines**. Le site principal n'est ainsi pas touché.

---

## 1. Base de données

1. cPanel → **Bases de données MySQL** :
   - créer la base `precisfc` (cPanel la nomme `<compte>_precisfc`) ;
   - créer l'utilisateur `precisfc` (`<compte>_precisfc`) avec un mot de passe **généré** et noté en lieu sûr ;
   - ajouter l'utilisateur à la base avec **TOUS LES PRIVILÈGES**.
2. cPanel → **Terminal**. Passer la base en utf8mb4 (le serveur LWS est en latin1 par défaut) :
   ```bash
   mysql -u <compte>_precisfc -p -e "ALTER DATABASE <compte>_precisfc CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
   mysql -u <compte>_precisfc -p -e "SELECT @@character_set_database, @@default_storage_engine;" <compte>_precisfc
   ```
   Résultat attendu : `utf8mb4`. Le moteur InnoDB est de toute façon imposé par Django.

## 2. Clé de déploiement GitHub (accès en lecture seule au dépôt privé)

Dans le Terminal cPanel :

```bash
ssh-keygen -t ed25519 -C "lws-precisfc-deploy" -f ~/.ssh/precisfc_deploy -N ""
cat ~/.ssh/precisfc_deploy.pub
```

Copier la ligne affichée, puis dans GitHub : dépôt `precisfc` → **Settings** → **Deploy keys** → **Add deploy key**. Titre : `LWS`. Coller la clé. **Ne pas** cocher « Allow write access ».

Toujours dans le Terminal :

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-precisfc
    HostName github.com
    User git
    IdentityFile ~/.ssh/precisfc_deploy
    IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
ssh -T git@github-precisfc      # répondre « yes » ; message attendu : « successfully authenticated »
```

> Si la connexion échoue (port 22 bloqué par l'hébergeur), remplacer dans `~/.ssh/config` : `HostName ssh.github.com` et ajouter la ligne `Port 443`.

## 3. Récupération du code

```bash
git clone git@github-precisfc:<identifiant-github>/precisfc.git ~/precisfc
mkdir -p ~/precisfc/logs ~/precisfc_private
chmod 700 ~/precisfc_private
```

## 4. Application Python (cPanel → Setup Python App)

**Create Application** :

| Champ | Valeur |
|---|---|
| Python version | **3.13.13** |
| Application root | `precisfc` |
| Application URL | `<domaine>` |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |
| Passenger log file | `/home/<compte>/precisfc/logs/passenger.log` |

Cliquer sur **Create**. En haut de la page, cPanel affiche une commande du type
`source /home/<compte>/virtualenv/precisfc/3.13/bin/activate && cd /home/<compte>/precisfc` : la noter.

> Si cPanel a remplacé `passenger_wsgi.py` par son propre fichier : `cd ~/precisfc && git checkout -- passenger_wsgi.py`

## 5. Fichier de configuration `.env`

```bash
cd ~/precisfc
source /home/<compte>/virtualenv/precisfc/3.13/bin/activate
python -c "import secrets; print(secrets.token_urlsafe(50))"   # clé secrète à copier
nano .env
```

Contenu (adapter chaque valeur) :

```ini
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=<clé générée ci-dessus>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<domaine>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<domaine>
DJANGO_ADMIN_URL=<chemin-secret>/
DJANGO_ADMINS=<votre adresse e-mail>
DATABASE_URL=mysql://<compte>_precisfc:<mot de passe encodé>@localhost:3306/<compte>_precisfc
STATIC_ROOT=<racine-web>/static
MEDIA_ROOT=<racine-web>/media
PRIVATE_MEDIA_ROOT=/home/<compte>/precisfc_private
LOG_DIR=/home/<compte>/precisfc/logs
CACHE_URL=dbcache://django_cache
CELERY_TASK_ALWAYS_EAGER=True
EMAIL_URL=consolemail://
```

Puis : `chmod 600 .env`.

> La première ligne est indispensable : sans elle, `python manage.py` charge les réglages de développement et échoue avec « No module named 'debug_toolbar' ».

> Dans le mot de passe de `DATABASE_URL`, encoder les caractères spéciaux : `@` → `%40`, `:` → `%3A`, `/` → `%2F`, `#` → `%23`.

## 6. Installation et initialisation

```bash
cd ~/precisfc && source /home/<compte>/virtualenv/precisfc/3.13/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.prod

pip install --upgrade pip
pip install -r requirements/cpanel.txt
python -c "import config; print('Pilote MySQL :', config.MYSQL_DRIVER)"   # attendu : pymysql

python manage.py check --deploy --database default   # seul avertissement attendu : security.W004 (HSTS)
python manage.py migrate
python manage.py createcachetable
python manage.py collectstatic --noinput
python manage.py createsuperuser

mkdir -p <racine-web>/media
cp deploy/cpanel/static.htaccess <racine-web>/static/.htaccess
cp deploy/cpanel/media.htaccess  <racine-web>/media/.htaccess

mkdir -p tmp && touch tmp/restart.txt
```

## 7. Vérifications

| # | Vérification | Résultat attendu |
|---|---|---|
| 1 | `https://<domaine>/healthz/` | `{"status": "ok"}` |
| 2 | `https://<domaine>/<chemin-secret>/` | Page de connexion de l'administration, **avec sa mise en forme** (preuve que les fichiers statiques sont servis) |
| 3 | Connexion avec le super administrateur | Tableau de bord Django Admin |
| 4 | `curl -sI https://<domaine>/static/admin/css/base.css \| grep -i cache-control` | `public, max-age=31536000, immutable` (fichier servi par Apache, pas par Django) |
| 5 | `curl -sI http://<domaine>/healthz/ \| head -1` | Redirection `301` vers HTTPS |
| 6 | `python manage.py run_scheduled_jobs` | `apps.core.jobs.clear_expired_sessions : réussie` |

## 8. Tâche cron (cPanel → Tâches Cron)

Réglage « Toutes les 5 minutes » (`*/5 * * * *`), commande :

```bash
cd /home/<compte>/precisfc && /home/<compte>/virtualenv/precisfc/3.13/bin/python manage.py run_scheduled_jobs --settings=config.settings.prod >> /home/<compte>/precisfc/logs/cron.log 2>&1
```

## 9. En cas de problème

| Symptôme | Où regarder / quoi faire |
|---|---|
| Erreur 500 ou « Web application could not be started » | `tail -50 ~/precisfc/logs/passenger.log` et `~/precisfc/logs/errors.log` |
| `core.E001` (jeu de caractères) | Refaire le `ALTER DATABASE` de l'étape 1 (avant `migrate`) |
| `Access denied` sur la base | Vérifier l'utilisateur, le mot de passe encodé, et les privilèges dans cPanel |
| `Can't connect … through socket` / connexion refusée | Remplacer `localhost` par `127.0.0.1` dans `DATABASE_URL` (ou l'inverse) |
| Page d'admin sans mise en forme, ou erreur 500 sur `/static/` | Retirer la ligne `PassengerEnabled off` de `<racine-web>/static/.htaccess` (non supportée par certains serveurs LiteSpeed) ; WhiteNoise sert alors les fichiers |
| `No module named 'debug_toolbar'` | Les réglages de développement ont été chargés : ajouter `DJANGO_SETTINGS_MODULE=config.settings.prod` en tête du `.env` (étape 5) |
| `Failed to build 'mysqlclient'` pendant `pip install` | Version de `requirements/cpanel.txt` antérieure au 20/10/2026 : faire `git pull`. LWS ne permet pas de compiler mysqlclient ; PyMySQL le remplace |
| Modification non prise en compte | `touch ~/precisfc/tmp/restart.txt` |

## 10. Mises à jour suivantes

```bash
VENV=/home/<compte>/virtualenv/precisfc/3.13 bash ~/precisfc/deploy/scripts/deploy_cpanel.sh
```

Le script affiche le commit précédent. Retour arrière : `git checkout <commit>` puis `touch tmp/restart.txt`. La procédure complète, avec la restauration de la base, sera fournie à l'étape 16.

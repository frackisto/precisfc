# Étape 2 — Initialisation du projet

> Statut : **terminée** le 15/10/2026 (15 tests verts), en attente de validation.

## Ce qui a été mis en place

| Élément | Fichier(s) | Rôle |
|---|---|---|
| Dépôt Git | `.gitignore` | Branche `main`. `.env`, `.venv`, médias et fichiers privés sont exclus. |
| Dépendances figées | `requirements/base.txt`, `dev.txt`, `cpanel.txt`, `vps.txt` | Une liste par environnement, versions exactes (`==`) |
| Outillage | `pyproject.toml` | ruff (style, imports, règles de sécurité), pytest, coverage |
| Projet Django | `manage.py`, `config/` | Réglages séparés : `base` (commun), `dev`, `test`, `prod` |
| Pilote MySQL | `config/db_driver.py` | mysqlclient si disponible, sinon PyMySQL (pour LWS) |
| Configuration | `.env.example` → `.env` | Secrets et base de données hors du code |
| Application `core` | `apps/core/` | Route de contrôle `/healthz/` (sert aussi pour le déploiement LWS) |
| Base locale | MariaDB WAMP (port 3307) | Base `precisfc` en `utf8mb4_unicode_ci` et utilisateur dédié (droits limités à `precisfc` et `test_precisfc`) |

## Choix techniques

- **Réglages par environnement.** `manage.py` utilise `dev` par défaut. `wsgi.py`, et donc Passenger chez LWS, utilise `prod`. pytest utilise `test`.
- **Les réglages d'un environnement ne modifient jamais ceux de `base.py`.** Ils créent de nouvelles listes, sans `+=` ni `.insert()`. Ce défaut a été détecté par les tests pendant l'étape : charger les réglages de dev ajoutait la debug toolbar aux réglages de production en mémoire. Un test empêche désormais toute régression.
- **Connexion MariaDB.** Le jeu de caractères `utf8mb4` est imposé, en mode SQL strict et avec l'isolation `READ COMMITTED` recommandée par Django.
- **Mots de passe.** Ils sont hachés avec Argon2 en production. Les tests utilisent un hachage rapide, réservé aux tests.
- **Production sécurisée par défaut.** Cookies sécurisés et redirection HTTPS sont actifs. HSTS reste à 0 jusqu'à la validation du HTTPS chez LWS, comme l'exige le cahier des charges.
- **Applications tierces.** allauth, DRF, axes, etc. sont installées mais seront activées à l'étape où elles servent.

## Commandes exécutées (Windows)

```powershell
git init -b main
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements\dev.txt
.\.venv\Scripts\python.exe -m pip check
# .env créé depuis .env.example avec une clé secrète et un mot de passe de base aléatoires
# Base et utilisateur créés dans MariaDB WAMP (port 3307), en utf8mb4_unicode_ci
```

## Vérifications et résultats

| Contrôle | Commande | Résultat |
|---|---|---|
| Conflits de dépendances | `pip check` | `No broken requirements found.` |
| Qualité du code | `ruff check .` et `ruff format --check .` | Aucun problème |
| Contrôles Django (dev) | `python manage.py check` | `no issues` |
| Contrôles Django (prod) | `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check` | `no issues` |
| Tests | `pytest` | **15 réussis** |
| Serveur | `python manage.py runserver` puis `/healthz/` | `HTTP 200 {"status": "ok"}` |

## Pour reproduire sur votre poste

```powershell
cd C:\MesProjets\precisfc
.\.venv\Scripts\Activate.ps1
python manage.py check
pytest
python manage.py runserver      # puis ouvrir http://127.0.0.1:8000/healthz/
```

## Point d'attention pour l'étape 3

Aucune migration n'a encore été appliquée, volontairement. Le **modèle utilisateur personnalisé** (`accounts.User`) doit exister **avant le tout premier `migrate`**. Sinon, les tables d'authentification standard de Django seraient créées et ne pourraient plus être remplacées proprement.

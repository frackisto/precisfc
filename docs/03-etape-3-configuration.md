# Étape 3 — Base de données, configuration, fichiers, tâches

> Statut : **partie locale terminée** (49 tests verts, couverture 97 %). Reste le **déploiement de test chez LWS** ([deploiement-cpanel.md](deploiement-cpanel.md)).

## Ce qui a été mis en place

| Élément | Fichier(s) | Détail |
|---|---|---|
| Utilisateur personnalisé | `apps/accounts/` | Connexion par e-mail. L'adresse est normalisée en minuscules, et son unicité est insensible à la casse. Le modèle a été créé **avant le premier `migrate`**. |
| Base MariaDB | `config/settings/base.py` | utf8mb4, **InnoDB imposé à chaque connexion**, mode SQL strict, isolation READ COMMITTED |
| Contrôles système | `apps/core/checks.py` | `core.E001` : base pas en utf8mb4. `core.E002` : stockage privé dans un dossier public. `core.E003` : tables non InnoDB. |
| Stockage privé | `apps/core/storage.py` | Pas d'URL publique ; fichiers en `0600` ; alias `storages["private"]` |
| Cache | `CACHE_URL` | Table en base sur cPanel ; Redis sur un VPS en changeant une seule variable |
| Celery | `config/celery.py`, `apps/core/tasks.py` | Exécution immédiate sur cPanel ; worker activable sur un VPS |
| Tâches périodiques | `apps/core/scheduling.py`, `run_scheduled_jobs` | Une seule ligne cron. Chaque application déclare ses tâches dans `jobs.py`. Un verrou atomique empêche les exécutions simultanées, et une tâche en échec est retentée au passage suivant. |
| E-mails | `EMAIL_URL` | Console en local ; SMTP LWS en production |
| Journalisation | `prod.py` | `logs/django.log` et `logs/errors.log` (rotation 5 × 5 Mo), alerte e-mail sur les erreurs 500 |
| Téléversements | `MAX_UPLOAD_SIZE` | 8 Mo par défaut (limite appliquée par les formulaires à partir de l'étape 9) |
| Déploiement cPanel | `passenger_wsgi.py`, `deploy/cpanel/*.htaccess`, `deploy/scripts/deploy_cpanel.sh` | Point d'entrée Passenger, fichiers statiques servis par Apache, aucun script exécutable dans les médias, script de mise à jour |

## Problème détecté et corrigé : tables MyISAM

Le MariaDB de WAMP est configuré avec `default_storage_engine=MYISAM` (dans `my.ini`). Les premières tables ont donc été créées en **MyISAM**, un moteur **sans transactions ni verrous de ligne**. Sur cette base, la protection contre les doubles réservations et la survente aurait été inopérante.

Correction, sans toucher à la configuration de WAMP (que d'autres projets peuvent utiliser) :
1. Django impose `default_storage_engine=INNODB` à chaque connexion, quel que soit le réglage du serveur.
2. Le contrôle `core.E003` bloque `check --database` et le script de déploiement si une table n'est pas en InnoDB. Il a bien détecté les 11 tables MyISAM avant la correction.
3. La base locale, encore vide, a été recréée. Les 12 tables sont désormais en InnoDB.
4. Un test vérifie qu'une transaction annulée ne laisse aucune trace, ce qui serait impossible avec MyISAM.

## Vérifications et résultats

| Contrôle | Résultat |
|---|---|
| `ruff check` / `ruff format --check` | Aucun problème |
| `manage.py check --database default` | Aucun problème |
| `makemigrations --check` | Aucune migration manquante |
| `check --deploy` avec les réglages de production | Uniquement `security.W004` (HSTS), **volontaire** jusqu'à la validation du HTTPS |
| `collectstatic` en production | 127 fichiers, avec empreintes pour le cache |
| `run_scheduled_jobs` (2 passages) | « réussie », puis « pas encore due » |
| `pytest --cov` | **49 réussis**, couverture **97 %** |
| Serveur de dev | `/healthz/` 200, page de connexion admin 200, CSS 200 |

## Tests ajoutés (34)

- **Comptes (10)** : normalisation de l'e-mail, hachage, unicité insensible à la casse imposée par la base, connexion avec une casse différente, super administrateur, création d'un utilisateur via l'admin.
- **Base (7)** : utf8mb4 et InnoDB, toutes les tables en InnoDB, aller-retour d'accents et d'emoji, annulation de transaction, contrôles E001 et E003.
- **Stockage privé (5)** : enregistrement hors des dossiers publics, absence d'URL, 404 sur tout chemin d'accès, contrôle E002.
- **Planificateur (8)** : première exécution, intervalle respecté, nouvelle tentative après un échec, verrou et expiration du verrou, mode forcé, commande (liste, exécution, échec, tâche inconnue).
- **Services (3)** : Celery synchrone, cache en base, journaux de production.
- **Projet (2)** : point d'entrée Passenger, modèle utilisateur.

# Étape 5 — Comptes, connexion sécurisée, 13 rôles

> Statut : **terminée et validée** (20/10/2026). 665 tests réussis, couverture 97 %.

## Comptes des supporters (django-allauth)

| Élément | Comportement |
|---|---|
| Inscription | `/compte/signup/` : e-mail + mot de passe (10 caractères minimum, ni trop courant ni trop proche de l'e-mail) |
| Vérification de l'e-mail | **Obligatoire** : sans clic sur le lien reçu, la connexion est refusée |
| Connexion | `/compte/login/`, par e-mail, sans tenir compte des majuscules |
| Mot de passe oublié | `/compte/password/reset/` |
| Mon compte | `/compte/profil/` : nom, téléphone (format ivoirien +225), ville, préférences de notification. Chaque supporter ne voit que le sien |
| Profil | Créé automatiquement avec chaque compte (et ajouté aux comptes existants par une migration) |
| Hachage | Argon2 |
| Inscriptions en production | **Fermées** (`DJANGO_SIGNUP_OPEN=False`) tant que l'envoi d'e-mails n'est pas configuré : sans SMTP, les e-mails de vérification ne partiraient pas |

Les pages ont la présentation brute d'allauth : le thème du club arrive à l'étape 6.

## Protection contre les tentatives répétées

| Protection | Règle |
|---|---|
| **django-axes** (principale) | Au **5e échec** pour un même compte depuis une même connexion, blocage de **30 minutes**, même avec le bon mot de passe. S'applique au site et à l'administration |
| Limiteur d'allauth (filet) | 20 échecs par compte en 15 minutes, toutes connexions confondues (attaque répartie sur de nombreuses adresses IP) |

**Problème détecté par les tests et corrigé.** Par défaut, allauth bloque un compte après 5 échecs **quelle que soit la connexion**. N'importe qui aurait pu empêcher un supporter de se connecter en tapant son adresse avec de mauvais mots de passe. Le seuil d'allauth a été relevé : c'est axes, qui bloque le couple compte + connexion, qui protège en premier.

## Les 13 rôles

| Rôle | Peut | Ne peut pas (exemples testés) |
|---|---|---|
| **Super administrateur** | Tout (superutilisateur Django) | — |
| **Direction** | Consulter indicateurs, commandes, paiements, contenus | Modifier quoi que ce soit ; voir les candidatures d'enfants |
| **Administrateur du club** | Contenus, équipes, matchs, partenaires, paramètres, publier | Paiements, comptes utilisateurs, candidatures |
| **Responsable communication** | Relire et publier les articles, médias, bannières, newsletter | Matchs, commandes |
| **Rédacteur** | Écrire des articles et modifier **ses brouillons** | Publier, supprimer, modifier un article en relecture ou d'un autre |
| **Gestionnaire médias** | Albums, photos, vidéos | Articles, joueurs |
| **Responsable sportif** | Équipes, joueurs, staff, compétitions, matchs | Articles, commandes, classements (calculés) |
| **Entraîneur** | Compositions, événements, statistiques et joueurs **de son équipe** | Les autres équipes ; créer un joueur ; supprimer un match |
| **Responsable boutique** | Catalogue, stocks (par mouvements), commandes, livraison, codes promo, retours | Supprimer une commande, confirmer un paiement |
| **Trésorier** | **Confirmer les paiements manuels**, indicateurs financiers | Modifier un paiement ou une commande |
| **Responsable billetterie** | Catégories de places, prix, quotas, réservations, contrôle | Confirmer un paiement, supprimer une réservation |
| **Agent de contrôle** | **Contrôler les billets**, rien d'autre | Administration, réservations, tableau de bord |
| **Responsable du centre de formation** | Centre, candidatures, **documents privés** | Supprimer une candidature, paiements |

- Les groupes sont créés et tenus à jour par `python manage.py setup_roles` (idempotente, lancée par le script de déploiement). Les permissions d'un groupe sont **exactement** celles du code : une permission ajoutée à la main est retirée au déploiement suivant.
- **L'accès à l'administration découle des rôles** : la case « statut équipe » n'est plus modifiable. Elle est cochée automatiquement pour les rôles internes (sauf l'agent de contrôle) et décochée quand le dernier rôle est retiré.
- Seul le super administrateur gère les comptes et attribue les rôles (pas d'élévation de privilèges possible).

## Règles par objet (`apps/accounts/permissions.py`)

Appliquées dès maintenant dans l'administration, et réutilisées par le tableau de bord et l'API :
- un **entraîneur** ne modifie que les matchs et joueurs de l'équipe à laquelle il est rattaché (fiche staff liée à son compte). Les autres sont visibles en lecture seule, et un envoi forcé est refusé (403) ;
- un **rédacteur** ne modifie que ses propres brouillons. Statut, date de publication et « à la une » sont en lecture seule pour lui, et il est automatiquement l'auteur de ses articles ;
- confirmer un paiement manuel, contrôler un billet, télécharger un document privé : réservés au rôle concerné (fonctions prêtes pour les étapes 13 et 14).

## Problème signalé pendant la démonstration et corrigé

`/admin/axes/accesslog/` affichait « Database returned an invalid datetime value ». Toute liste de l'administration avec un filtre par date (matchs, commandes, articles…) aurait eu la même erreur dès qu'elle contenait des données. Les tests ne l'avaient pas vu, car leurs tables étaient vides.

- **Cause** : pour regrouper par jour ou par mois, Django demandait à MariaDB de convertir les dates d'UTC vers `Africa/Abidjan` (`CONVERT_TZ`). Cette fonction exige les tables de fuseaux horaires de MariaDB, absentes de WAMP et impossibles à installer sur l'hébergement mutualisé LWS.
- **Correction** : la base est déclarée dans le fuseau du club (`DATABASES["default"]["TIME_ZONE"]`). Abidjan étant toujours à UTC+0, les valeurs stockées ne changent pas, et Django n'a plus besoin de conversion.
- **Tests ajoutés (4)** : regroupement par mois, liste de l'administration avec des données, valeurs stockées inchangées, et un garde-fou qui échoue si le fuseau du club venait à changer pour un fuseau à décalage.

## Vérifications et résultats

| Contrôle | Résultat |
|---|---|
| `ruff check` / `ruff format --check` | Aucun problème |
| `manage.py check` | Aucun problème |
| `check --deploy` (production) | Uniquement `security.W004` (HSTS), volontaire |
| `makemigrations --check` | Aucune migration manquante |
| `pytest --cov` | **665 réussis**, couverture **97 %** |

Avertissement masqué : `models.W036`. allauth déclare des index uniques partiels que MariaDB ne connaît pas. C'est sans conséquence, car `User.email` est unique en base. Un test garantit qu'aucun modèle du projet n'en dépend.

## Tests ajoutés (141)

- **Rôles** : chaque rôle a les droits attendus et **n'a pas** des droits sensibles choisis (matrice testée pour les 12 groupes), accès à l'administration selon le rôle, idempotence de `setup_roles`.
- **Règles par objet** : entraîneur (son équipe / autre équipe, y compris un envoi forcé), rédacteur (ses brouillons, pas de publication possible depuis l'administration).
- **Authentification** : inscription, e-mail de vérification, connexion refusée avant vérification, lien de confirmation, inscriptions fermées, verrouillage au 5e échec (même avec le bon mot de passe), sans tenir compte des majuscules, sans bloquer le compte depuis une autre connexion, remise à zéro après une connexion réussie, administration protégée aussi, attaque répartie freinée.
- **Mon compte** : accès réservé aux personnes connectées, modification de son propre profil.

## Déploiement

Le script `deploy_cpanel.sh` lance désormais `setup_roles` après les migrations. Rien à ajouter au `.env` du serveur : les inscriptions sont fermées par défaut en production.

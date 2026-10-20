# Étape 4 — Applications, modèles, migrations, administration de base

> Statut : **terminée et validée** (20/10/2026). 524 tests réussis, couverture 97 %. Les 9 types d'articles et les critères de départage par défaut sont acceptés pour l'instant.

## Ce qui a été mis en place

### 16 applications

`core`, `accounts` (existantes) et 14 nouvelles : `teams`, `competitions`, `matches`, `news`, `media_library`, `shop`, `orders`, `payments`, `ticketing`, `academy`, `partners`, `contact`, `notifications`, `dashboard` (sans modèle, pour le tableau de bord de l'étape 10). L'API (`api/v1/`) arrive à l'étape 11.

### 68 modèles

| Application | Modèles |
|---|---|
| `core` (11) | `ClubSettings` (fiche unique), `Facility`, `FacilityPhoto`, `HeroSlide`, `Page`, `Value`, `Trophy`, `TrophyWin`, `President`, `OrgMember`, `ScheduledJobRun` |
| `accounts` (3) | `User`, `Profile`, `Address` |
| `teams` (4) | `Team`, `Player`, `PlayerPhoto`, `Staff` |
| `competitions` (7) | `Season`, `Club`, `Competition`, `CompetitionSeason`, `Participation`, `Standing`, `PlayerSeasonStat` |
| `matches` (5) | `Match`, `MatchScheduleChange`, `LineupEntry`, `MatchEvent`, `MatchTeamStat` |
| `news` (3) | `Category`, `Tag`, `Article` |
| `media_library` (3) | `Album`, `Photo`, `Video` |
| `shop` (6) | `ProductCategory`, `Product`, `ProductImage`, `ProductVariant`, `StockMovement`, `WishlistItem` |
| `orders` (9) | `Cart`, `CartItem`, `ShippingMethod`, `PromoCode`, `PromoRedemption`, `Order`, `OrderItem`, `OrderStatusEvent`, `ReturnRequest` |
| `payments` (2) | `Payment`, `WebhookEvent` |
| `ticketing` (4) | `TicketCategory`, `Booking`, `Ticket`, `TicketScan` |
| `academy` (5) | `AgeCategory`, `TrainingProgram`, `AcademyEvent`, `Application`, `ApplicationDocument` |
| `partners` (1), `contact` (2), `notifications` (3) | `Partner` ; `ContactMessage`, `FaqItem` ; `NewsletterSubscriber`, `NewsletterCampaign`, `EmailLog` |

### Socle commun (`apps/core`)

| Élément | Rôle |
|---|---|
| `TimeStampedModel` | `created_at`, `updated_at` sur toutes les tables (sauf `User` et `ScheduledJobRun`) |
| `SluggedModel` | Slug unique généré au premier enregistrement (« Stade Félix » → `stade-felix`, puis `stade-felix-2`…), **jamais modifié ensuite** pour ne pas casser les liens |
| `SEOFields` | Titre, description et image de partage (pages, articles, produits) |
| `SingletonModel` | Une seule ligne (`ClubSettings.load()`) |
| `RandomFilename` | Fichiers privés renommés au hasard : le nom d'un enfant n'apparaît jamais sur le disque |
| `private_storage` | Candidatures et pièces jointes de contact dans le stockage privé, sans URL |
| `URLField` | Une adresse saisie sans `https://` est complétée en `https://` |

## Règles protégées par la base de données

La base refuse elle-même les données incohérentes, même si un futur code oublie une vérification (127 contraintes CHECK créées dans MariaDB, en plus des contraintes d'unicité).

| Domaine | Règles |
|---|---|
| Joueurs | Numéro de maillot unique dans une équipe ; **un mineur sans consentement n'apparaît pas sur le site public**, et avec consentement seule son année de naissance s'affiche |
| Matchs | Un club ne joue pas contre lui-même ; un match terminé a un score ; tirs au but saisis des deux côtés ; un remplacement indique le joueur sortant |
| Classements | Une seule saison en cours ; victoire > nul ≥ défaite ; un ajustement de points est motivé ; joués = gagnés + nuls + perdus |
| Boutique | **Le stock ne peut jamais devenir négatif** ; prix promotionnel inférieur au prix normal ; SKU unique |
| Commandes | Total = sous-total − réduction + livraison ; ligne = prix × quantité ; un code promo ne dépasse jamais son nombre d'utilisations |
| Paiements | Un paiement concerne une commande **ou** une réservation ; **un numéro de transaction Mobile Money ne valide qu'un seul paiement** ; un paiement réussi est daté ; notification d'agrégateur traitée une seule fois |
| Billetterie | Code de billet unique et imprévisible ; une réservation en attente a une échéance ; un billet utilisé est daté |
| Centre de formation | Consentement obligatoire ; **représentant légal obligatoire pour un mineur** (contrôle du formulaire, l'âge changeant avec le temps) |

## Administration de base

Tous les modèles sont accessibles dans l'administration, en français, avec recherche, filtres et formulaires imbriqués (photos, compositions, événements de match…). Quelques choix :

- **Paramètres du club** : un seul formulaire, ni ajout ni suppression.
- **Commandes, paiements, réservations, contrôles de billets, mouvements de stock** : **consultation seule**. Ces données ne doivent changer qu'à travers les services métier (étapes 12 et 13), qui tiennent stock, quotas et historique à jour et tracent l'agent.
- **Candidatures et messages de contact** : seul le suivi est modifiable ; les fichiers privés n'ont pas de lien (téléchargement contrôlé à l'étape 14).
- **Classements et statistiques** : calculés, donc en lecture seule.

## Vérifications et résultats

| Contrôle | Résultat |
|---|---|
| `ruff check` / `ruff format --check` | Aucun problème |
| `manage.py check --database default` | Aucun problème |
| `check --deploy` (production) | Uniquement `security.W004` (HSTS), volontaire |
| `makemigrations --check` | Aucune migration manquante |
| Tables non InnoDB | 0 |
| `pytest --cov` | **524 réussis**, 17 ignorés volontairement (formulaires d'ajout désactivés, exceptions documentées), couverture **97 %** |

## Problème détecté par les tests et corrigé

Enregistrer une nouvelle instance de `ClubSettings` alors que la fiche existait déjà provoquait une erreur : Django tentait une mise à jour avec une date de création vide. `SingletonModel.save()` conserve maintenant la date d'origine.

## Tests ajoutés (490, dont les variantes paramétrées)

- **Contraintes en base** : chaque règle du tableau ci-dessus est testée en écrivant directement en base (sans passer par les formulaires), pour prouver que MariaDB la refuse.
- **Slugs, fiche unique, confidentialité des mineurs, vidéos** (seul l'identifiant YouTube, Vimeo ou Dailymotion est accepté, jamais une URL ou du code HTML), **documents privés** (nom aléatoire, pas d'URL).
- **Administration** : chaque liste et chaque formulaire d'ajout s'ouvre pour un super administrateur, sur les 50 écrans.
- **Conventions** : les 16 applications sont installées ; chaque modèle est horodaté, nommé en français et lisible ; montants en `DECIMAL(12,2)` ; colonnes indexées ≤ 255 caractères.

## Reporté aux étapes suivantes (prévu au plan)

| Élément | Étape |
|---|---|
| Création automatique du profil, allauth, rôles | 5 |
| Éditeur riche et assainissement HTML des contenus | 9 |
| Déclinaisons WebP des photos (django-imagekit), historique des articles (auditlog) | 9 |
| Calcul des classements et statistiques | 8 |
| Services panier, commande, stock, paiement, réservation, contrôle | 12 et 13 |

## À valider

1. **Les 9 types d'articles** (le cahier des charges n'est pas dans le dépôt) : Actualité, Communiqué officiel, Avant-match, Compte rendu de match, Interview, Transfert, Centre de formation, Partenaires, Événement.
2. **Critères de départage par défaut** d'une nouvelle compétition, après les points : différence de buts générale, buts marqués, points puis différence de buts en confrontations directes. Modifiables par compétition.

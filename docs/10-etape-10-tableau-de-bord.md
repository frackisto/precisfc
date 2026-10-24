# Étape 10 — Tableau de bord et administration

> Statut : **terminée et validée** (24/10/2026). 1226 tests réussis, couverture 97 %.

## Tableau de bord `/gestion/`

Réservé aux personnes connectées qui ont un rôle interne. Un supporter, un visiteur ou l'agent de contrôle des billets reçoit un refus (403). Chaque page vérifie aussi sa propre permission **côté serveur**. Les pages ne sont jamais mises en cache ni indexées (`noindex`, `X-Robots-Tag`, `Disallow: /gestion/` dans robots.txt).

Le lien « Gestion » apparaît dans l'en-tête du site pour les rôles concernés. L'administration Django reste accessible depuis le tableau de bord, et inversement.

### Vue d'ensemble : les 11 indicateurs de la section 15 du cahier des charges

| Indicateur | Calcul exact | Visible par |
|---|---|---|
| Joueurs, équipes | Toutes les fiches | qui peut consulter joueurs / équipes |
| Matchs | Matchs de notre club sur la saison en cours (annulés exclus), « dont N joués » | rôles sportifs, communication, rédaction, médias, billetterie |
| Derniers résultats, prochains matchs | 5 derniers matchs terminés, 5 prochains (section Sport) | idem |
| Articles publiés | Articles visibles du public (publiés, ou programmés dont l'heure est passée) | rôles éditoriaux |
| Commandes | Toutes les commandes, et celles du mois | boutique, trésorier |
| **Chiffre d'affaires** | **Uniquement les paiements confirmés** (statut « réussi »), **à leur date de confirmation**. Initiés, en attente, échoués, annulés, expirés et **remboursés** n'y figurent jamais | direction, trésorier |
| Billets vendus | Billets valides ou utilisés des réservations confirmées (réservations en attente, expirées ou annulées exclues, billets annulés exclus) | billetterie, trésorier |
| Produits en rupture de stock | Produits en vente dont **plus aucune** variante n'est disponible, et nombre de variantes épuisées (une taille peut manquer) | boutique |
| Utilisateurs inscrits | Comptes actifs | administrateur du club |

La **direction** voit tous les compteurs, y compris supporters, messages et candidatures, grâce à une nouvelle permission `core.view_all_indicators` : ce sont des **chiffres agrégés**, sans aucun accès aux fiches personnelles (candidatures d'enfants, comptes, messages), qu'elle ne peut toujours pas ouvrir.

### Sections détaillées (selon le rôle)

| Section | Contenu |
|---|---|
| **À traiter** | Le travail en attente de chacun, avec le lien vers la liste déjà filtrée : articles à relire, mes brouillons (rédacteur), scores à saisir, paiements manuels à confirmer, commandes à préparer, retours, articles en stock bas, réservations en attente, candidatures à examiner, candidatures dont la durée de conservation est dépassée, messages non traités |
| **Raccourcis** | Écrire un article, programmer un match, ajouter un joueur, un album, une vidéo, une bannière, un produit, ouvrir une vente de billets, préparer une newsletter, paramètres du club, comptes et rôles : uniquement ceux que le rôle a le droit de faire |
| **Finances** | Chiffre d'affaires de l'année, panier moyen du mois (CA boutique ÷ commandes payées), paiements manuels à confirmer (nombre et montant), répartition boutique / billetterie, **graphique des 12 derniers mois** |
| **Boutique** | Commandes à préparer, en attente de paiement, expédiées, retours en cours, meilleures ventes du mois (commandes payées uniquement), tableau du stock bas (seuil d'alerte **compris**) |
| **Billetterie** | Pour chaque prochain match en vente : places, vendus, **taux de remplissage**, places bloquées par des réservations en attente encore valides, places restantes ; recette confirmée par match pour les seuls rôles financiers |
| **Sport** | Bilan de la saison (joués, victoires, nuls, défaites, buts), rang dans chaque classement, derniers résultats, prochains matchs |
| **Contenus** | Articles en relecture, programmés, publiés ce mois-ci, brouillons ; albums, photos, vidéos |
| **Supporters, contacts, académie** | Comptes, nouveaux comptes du mois, abonnés confirmés à la newsletter, messages nouveaux et en cours, candidatures à examiner, invités à un essai, conservation dépassée |

### Rapport financier `/gestion/finances/` (direction, trésorier)

- Période au choix (du… au…, trois ans au plus) ou raccourcis : ce mois-ci, le mois dernier, cette année, 12 derniers mois. Une période invalide affiche un message et revient au mois en cours.
- Chiffre d'affaires, boutique, billetterie, panier moyen, paiements à confirmer ; évolution sur 12 mois ; répartition par moyen de paiement (graphique et tableau).
- Détail de chaque paiement confirmé (tableau triable et filtrable) et **export CSV** lisible directement par Excel (accents, séparateur « ; »). Les cellules qui commencent par `=`, `+`, `-` ou `@` sont neutralisées (protection contre l'injection de formules dans le tableur).

### Saisie rapide des scores `/gestion/scores/`

- Matchs dont le coup d'envoi est passé et pas encore terminés, et matchs terminés depuis 14 jours (pour corriger une erreur).
- Score, tirs au but éventuels, statut « terminé » ou « en cours ». Les règles de la base sont vérifiées (tirs au but des deux équipes, score obligatoire pour un match terminé).
- **Le classement et les statistiques sont recalculés** dès l'enregistrement (mécanisme de l'étape 8).
- Un **entraîneur ne voit et ne saisit que les matchs de son équipe** (un autre match lui répond « introuvable »).
- Chaque modification d'un match est désormais **historisée avec son auteur** (journal d'audit), comme les articles.

### Tableaux et graphiques

- **DataTables 2.3.8** (et son intégration Bootstrap 5) ajouté dans `static/vendor/datatables/`, téléchargé depuis le registre npm officiel, **empreintes sha512 vérifiées**. Textes en français. Sans JavaScript, les tableaux restent complets.
- Graphiques **Chart.js** aux couleurs du club, lisibles en mode sombre, montants en FCFA. Chaque graphique a ses chiffres dans un tableau voisin (accessibilité, fonctionnement sans JavaScript).
- Montants affichés sans décimales et groupés par milliers avec une espace insécable (« 15 000 FCFA ») : nouveau filtre `fcfa`, réutilisé par la boutique à l'étape 12.

### Ce qui viendra aux étapes suivantes

Les **actions** sur les commandes, les paiements, les billets et les candidatures (confirmer un paiement manuel, faire avancer une commande, émettre un billet) dépendent des services métier des étapes 12 à 14. Le tableau de bord les **affiche et les compte déjà**, avec un lien vers la liste filtrée de l'administration. Les boutons d'action s'ajouteront à ces mêmes écrans, avec leur traçabilité.

## Administration Django personnalisée

- **Nom du club** dans l'en-tête et le titre des pages (lu dans les Paramètres du club), logo et icône d'onglet du club.
- **Couleurs du club** sur l'en-tête, le fil d'Ariane et les boutons (variables du thème déjà contrôlées pour le contraste), en mode clair comme en mode sombre.
- Rubriques dans un **ordre métier** : le club, les équipes, les compétitions, les matchs, les actualités, les médias, les partenaires, la boutique, les commandes, les paiements, la billetterie, l'académie, le contact, la newsletter, puis les comptes et les journaux d'audit.
- Lien **« Tableau de bord »** dans la barre supérieure.
- Techniquement : `django.contrib.admin` est remplacé par sa configuration `apps.dashboard.admin_config.ClubAdminConfig` (même administration, aucun écran existant modifié).

## Démonstration

`python manage.py demo_dashboard` (après `demo_season` pour la billetterie) crée :

- une boutique de 4 produits (une écharpe en rupture, une taille en stock bas) ;
- 12 mois de commandes livrées et payées, plus des commandes à préparer, en attente de paiement (paiements manuels à confirmer), expédiées, annulées (paiement échoué) et **remboursées**, ainsi qu'une demande de retour ;
- la billetterie de 5 matchs de la saison de démonstration (3 joués, 2 à venir), avec réservations en attente ;
- 4 messages de contact, 5 candidatures (dont une à supprimer), 6 abonnés à la newsletter ;
- **4 comptes**, mot de passe `Demo-Precis-2026` : `direction@`, `tresorier@`, `boutique@` et `sportif@gestion.demo.precisfc.test`.

`--delete` supprime uniquement ces données. Réservée au développement. `demo_season --delete` supprime désormais aussi la billetterie de démonstration attachée à ses matchs.

Vérification sur la base de développement : chiffre d'affaires d'octobre **4 820 000 FCFA**, de l'année **8 760 000 FCFA**, **1 670 billets vendus** : chiffres identiques à ceux d'une requête SQL écrite à la main, indépendante du code. Le remboursement de 77 000 FCFA est bien exclu.

## Problèmes détectés et corrigés

| Problème | Correction |
|---|---|
| La direction (« consulte tous les indicateurs ») ne voyait pas les compteurs supporters, messages et candidatures, puisque ses droits excluent à juste titre ces fiches personnelles | Permission `core.view_all_indicators` : chiffres agrégés seulement, fiches toujours inaccessibles (testé) |
| Un match « terminé » daté plus tard dans la journée apparaissait dans « prochains matchs en vente » | Les matchs terminés sont exclus des ventes à venir (testé) |
| Après `demo_dashboard`, `demo_season --delete` aurait échoué (billets liés aux matchs, clés protégées) | La suppression de la saison emporte sa billetterie de démonstration (testé) |
| Une barre de progression Bootstrap aurait exigé un style en ligne, interdit par la future politique CSP (étape 15) | Élément HTML natif `<meter>` |

## Mise à jour du serveur LWS

Une migration s'ajoute (`core.0004`, nouvelle permission). Le script de déploiement lance déjà `migrate` puis `setup_roles`, qui donne la permission à la direction.

## Vérifications et résultats

| Contrôle | Résultat |
|---|---|
| `ruff check` / `ruff format --check` | Aucun problème |
| `makemigrations --check` | À jour (une migration ajoutée : `core.0004`) |
| `check --deploy` (production) | Uniquement `security.W004` (HSTS), volontaire |
| `collectstatic` en production | 425 fichiers (DataTables, styles de l'administration et script du tableau de bord ajoutés) |
| `pytest --cov` | **1226 réussis**, couverture **97 %** (module du tableau de bord : 91 à 99 % selon les fichiers) |

## Tests ajoutés (217)

- **Accès par rôle (96)** : visiteur renvoyé à la connexion, supporter et agent de contrôle refusés sur chaque page, compte désactivé refusé ; pour **chacun des 13 rôles** : accueil, rapport financier, export, saisie des scores (autorisés ou refusés), sections affichées et **seulement celles-là**, raccourcis, tâches ; aucun chiffre financier pour les autres rôles ; direction sans lien vers les fiches personnelles ; pages jamais mises en cache ni indexées.
- **Exactitude des indicateurs (47)** : chiffre d'affaires (les 6 statuts non confirmés exclus, remboursement compris), bornes de période à la microseconde, boutique et billetterie séparées, commandes comptées une fois, panier moyen arrondi, 12 mois avec les mois vides, moyens de paiement, paiements à confirmer, commandes et retours par statut, stock bas (seuil compris), rupture de stock, meilleures ventes (commandes payées de la période seulement), billetterie (vendus, en attente, expirés, annulés, contrôlés, recette, remplissage), matchs à saisir, portée de l'entraîneur, bilan de saison, articles, comptes, newsletter, messages, candidatures et conservation ; les 11 indicateurs du cahier des charges et leur visibilité par rôle ; nombre de requêtes SQL **constant** quel que soit le volume.
- **Rapport financier et export (22)** : période par défaut, invalide, trop longue, raccourcis, détail, CSV (en-têtes, accents, séparateur, contenu exact, commande et billetterie), **injection de formules neutralisée**, export refusé à la boutique.
- **Saisie des scores (14)** : enregistrement et **recalcul du classement**, historique avec l'auteur, match en cours, 5 saisies invalides refusées sans rien modifier, tirs au but, entraîneur limité à son équipe, jeton CSRF obligatoire.
- **Administration (9)** : site du club, nom et titre, couleurs, page de connexion, lien vers le tableau de bord, ordre des rubriques, formulaires intacts, DataTables hébergé sur le site.
- **Démonstration (7)** : refus hors développement, données cohérentes avec les indicateurs, billetterie de la saison de démonstration, comptes et connexion, pas de doublon, suppression ciblée, comptes de `demo_news` préservés.
- **Montants (10)** et **gabarits (12)** : format FCFA et arrondis ; les 6 nouveaux gabarits compilent.

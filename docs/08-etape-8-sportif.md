# Étape 8 — Équipes, joueurs, matchs, classements, statistiques

> Statut : **terminée et validée** (22/10/2026). 914 tests réussis, couverture 97 %.

## Pages publiques

| Adresse | Contenu |
|---|---|
| `/equipes/` | Équipes publiées |
| `/equipes/<équipe>/` | Effectif par poste, staff, prochains matchs, derniers résultats |
| `/joueurs/<joueur>/` | Fiche : poste, nationalité, date ou année de naissance, taille et poids (si autorisés), biographie, statistiques par saison et compétition, photos |
| `/matchs/` | Calendrier et résultats du club, avec **filtres** (saison, compétition, équipe, à venir / résultats), pagination par 20. Les filtres sont dans l'adresse : un lien filtré peut être partagé |
| `/matchs/<match>/` | Score, tirs au but, faits de jeu minute par minute, compositions, statistiques d'équipe, compte rendu, arbitres, affluence, vidéo, mention « initialement prévu le… » en cas de report |
| `/matchs/calendrier.ics` | Calendrier à ajouter à son agenda (téléphone, Google Agenda, Outlook), **avec les mêmes filtres** |
| `/matchs/calendrier.pdf` | Calendrier imprimable (PDF A4 paysage, aux couleurs du club) |
| `/competitions/` | Compétitions de la saison en cours |
| `/competitions/<compétition>/<saison>/` | Classement (par groupe s'il y en a), forme sur 5 matchs, meilleure attaque et défense, meilleurs buteurs (avec graphique) et passeurs |

« Équipes » et « Matchs » apparaissent dans le menu. Les cartes de match de l'accueil mènent à la page du match, et les joueurs vedettes à leur fiche. Ces pages sont ajoutées au plan du site.

## Confidentialité des mineurs

Un joueur mineur sans consentement de son représentant légal **n'apparaît nulle part** : ni dans l'effectif, ni dans le plan du site, ni dans les classements de buteurs et de passeurs ou leur graphique. Sa fiche renvoie une erreur 404, même par lien direct. Dans les compositions et les faits de jeu, son nom est remplacé par « Joueur du club », sans lien. Avec consentement : année de naissance seule, sans taille ni poids.

## Calculs automatiques

| Calcul | Règles |
|---|---|
| **Classement** | Matchs terminés entre participants d'un même groupe ; barème de la compétition ; ajustements de points (pénalités) ; puis les **critères de départage choisis pour la compétition, dans l'ordre**. Les confrontations directes sont calculées **uniquement entre les clubs encore à égalité** (mini-classement). En dernier recours, ordre alphabétique (jamais aléatoire) |
| **Statistiques des joueurs** | Matchs joués (titulaire, ou remplaçant entré en jeu), titularisations, minutes (entrée, sortie, expulsion), buts (hors contre son camp), passes, cartons (un second jaune compte un jaune et un rouge), matchs sans encaisser pour le gardien resté tout le match |
| **Recalcul** | Automatique dès qu'un match, une composition, un événement, un participant ou le barème change, **une fois l'enregistrement validé**. Deux recalculs simultanés s'exécutent l'un après l'autre. Commande de secours : `python manage.py recompute_standings` |
| **Reports** | Chaque changement d'horaire est conservé (ancien et nouvel horaire, motif, auteur). L'horaire initial reste affiché. Dans l'administration, un champ « Motif du changement d'horaire » est ajouté |

## Saison de démonstration

`python manage.py demo_season` crée une saison fictive complète : 8 clubs (dont le nôtre, réutilisé s'il existe), un championnat de 7 journées (les 5 premières jouées, avec compositions, buts, passes, cartons, remplacements et statistiques), un effectif de 20 joueurs dont **deux mineurs** (l'un sans consentement, masqué partout ; l'autre avec, année de naissance seule). Les données sont identiques à chaque exécution. Une nouvelle exécution recrée la saison sans doublon. `--delete` supprime tout ce qui a été créé (tout porte un slug « demo- ») et conserve notre club existant. Réservée au développement : refusée en production sans `--force`.

La saison de démonstration devient la saison en cours. Après `--delete`, il faut recocher « saison en cours » sur la vraie saison, s'il y en a une.

Pour la saisie en masse (cette commande, ou un futur import), le recalcul automatique peut être suspendu, puis lancé une seule fois à la fin (`recompute_suspended`).

## Problème détecté par les tests et corrigé

Le motif d'un report restait attaché au match : un changement d'horaire ultérieur aurait été enregistré avec l'ancien motif. Il est maintenant effacé une fois utilisé.

## Vérifications et résultats

| Contrôle | Résultat |
|---|---|
| `ruff check` / `ruff format --check` | Aucun problème |
| `makemigrations --check` | Aucune migration (seulement des requêtes, des services et des vues) |
| `check --deploy` (production) | Uniquement `security.W004` (HSTS), volontaire |
| `collectstatic` en production | 405 fichiers (Chart.js 4.5.1 ajouté, empreinte sha512 vérifiée) |
| Requêtes SQL | Calendrier ≤ 12 (20 matchs), classement ≤ 12 (15 joueurs) : ne croissent pas avec le volume |
| `pytest --cov` | **914 réussis**, couverture **97 %** |

## Tests ajoutés (84)

- **Classements (19)** : barème, ajustements, différence de buts, buts marqués, victoires, buts à l'extérieur, confrontations directes avant ou après la différence de buts, **égalité à trois résolue par un mini-classement qui ignore les matchs contre les autres clubs**, ordre alphabétique en dernier recours, matchs non terminés et non-participants ignorés, groupes séparés, coupes sans classement, recalcul automatique après un score ou un changement de barème, commande de recalcul.
- **Statistiques (7)** : minutes et remplacements, buts, passes et contre son camp, cartons et expulsion, matchs sans encaisser, recalcul automatique.
- **Reports (3)** : horaire initial conservé, historique, auteur et motif depuis l'administration.
- **Saison de démonstration (6)** : calendrier « chacun contre chacun », cohérence des scores et des buts, mineur masqué sur les pages, pas de doublon, suppression qui conserve notre club, refus en production.
- **Pages (49)** : équipes et joueurs (mineurs masqués partout, y compris par lien direct), calendrier et filtres, pagination, page de match (nom d'un mineur masqué), exports `.ics` (format, échappement, lignes de 75 octets, filtres) et PDF, classement, graphique, plan du site, nombre de requêtes.

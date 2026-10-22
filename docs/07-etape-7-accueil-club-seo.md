# Étape 7 — Accueil, pages du club, référencement

> Statut : **terminée et validée** (22/10/2026). 830 tests réussis, couverture 97 %.

## Pages publiques

| Adresse | Contenu |
|---|---|
| `/` | **Accueil** : bannières (carrousel ; la première seule sans JavaScript), prochain match et dernier résultat du club, 6 dernières actualités (« à la une » d'abord), joueurs vedettes, partenaires, présentation du club. Sans bannière, un bandeau aux couleurs du club |
| `/club/` | Présentation, chiffres clés (fondation, titres, stade), pages institutionnelles, valeurs |
| `/club/<page>/` | Page institutionnelle (histoire, mission, identité visuelle…) |
| `/club/palmares/` | Trophées remportés, avec saisons et nombre de titres |
| `/club/presidents/` | Présidents successifs |
| `/club/organigramme/` | Organigramme par département |
| `/club/infrastructures/` et `/club/infrastructures/<nom>/` | Stade, centres ; photos ; lien « Voir sur la carte » vers OpenStreetMap (sans clé ni traceur) |

Tout se gère dans l'administration. Ce qui n'est **pas publié** (page, infrastructure, membre de l'organigramme, match, article) n'apparaît nulle part et renvoie une erreur 404. Les bannières et les partenaires suivent leurs dates de début et de fin. Un article programmé apparaît à son heure, même si le cron n'est pas encore passé. Un **joueur mineur sans consentement** n'apparaît jamais.

Les rubriques non encore construites (matchs, actualités, joueurs) s'affichent sur l'accueil sans lien : les liens viendront avec leurs pages (étapes 8 et 9).

## Référencement

| Élément | Détail |
|---|---|
| Métadonnées | Titre, description (160 caractères, texte sans HTML) et image pour chaque page. Les champs SEO saisis dans l'administration sont prioritaires, puis le contenu, puis les valeurs par défaut des **Paramètres du club** |
| Open Graph | Titre, description, image, URL, type ; carte Twitter / X |
| URL canonique | Absolue, sans paramètres (`?utm_source=…`) |
| Schema.org | Le club en `SportsTeam` (logo, fondation, coordonnées, réseaux sociaux) ; fil d'Ariane en `BreadcrumbList` |
| Fil d'Ariane | Affiché sur les pages du club |
| `sitemap.xml` | Pages publiques uniquement, avec leur date de mise à jour. Chaque étape y ajoutera les siennes |
| `robots.txt` | Exclut les pages de compte ; indique le sitemap. **N'indique pas l'adresse de l'administration**, qui reste secrète |
| `noindex` | Pages de compte, « Mon compte », pages d'erreur |

## Problèmes détectés par les tests et corrigés

| Problème | Gravité | Correction |
|---|---|---|
| Les données structurées (Schema.org) n'échappaient pas `<` et `>` : un nom de club contenant `</script><script>…` aurait exécuté un script sur toutes les pages | **Faille de sécurité** (injection de script par une personne ayant accès aux paramètres du club) | Échappement identique au filtre `json_script` de Django ; un test tente l'injection |
| En français, les coordonnées s'affichaient avec une virgule (`5,316667`), ce qui cassait le lien vers la carte | Lien inutilisable | Coordonnées non localisées dans l'adresse |
| Un commentaire de gabarit sur plusieurs lignes se serait affiché sur la page | Texte parasite | Corrigé, et un test vérifie désormais tous les gabarits |

## Vérifications et résultats

| Contrôle | Résultat |
|---|---|
| `ruff check` / `ruff format --check` | Aucun problème |
| `makemigrations --check` | Aucune migration (seulement des requêtes et des vues) |
| `check --deploy` (production) | Uniquement `security.W004` (HSTS), volontaire |
| Requêtes SQL de l'accueil | **10 au plus**, quel que soit le nombre de bannières, articles, joueurs, partenaires ou matchs (testé avec 8 de chaque) |
| `pytest --cov` | **830 réussis**, couverture **97 %** |

## Bannières de démonstration

`python manage.py demo_banners` crée 4 bannières (identité du club, prochain match, boutique, académie) avec des images provisoires 1920 × 1080 aux couleurs du club, qui montrent la zone visible sur ordinateur et sur téléphone. `--delete` les supprime (images comprises) sans toucher aux autres bannières. Réservée au développement : refusée en production sans `--force`.

## Tests ajoutés (109)

- **Accueil** : bannières selon leurs dates, matchs de notre club uniquement (publiés), articles publiés ou programmés passés, aucun mineur sans consentement, partenaires en cours, nombre de requêtes borné.
- **Pages du club** : pages publiées seulement (404 sinon), texte échappé, priorité des adresses fixes, palmarès, présidents, organigramme, infrastructures et lien de carte, dates en français.
- **Référencement** : URL canonique, métadonnées des champs SEO puis valeurs par défaut, `noindex` sur les pages privées, données structurées (et tentative d'injection), fil d'Ariane, sitemap XML valide dont **chaque adresse répond**, `robots.txt` sans l'adresse de l'administration.
- **Gabarits** : tous compilent ; aucun commentaire sur plusieurs lignes.
- **Bannières de démonstration** : 4 bannières visibles en 1920 × 1080, pas de doublon, suppression ciblée, refus hors développement.

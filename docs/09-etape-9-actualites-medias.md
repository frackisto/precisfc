# Étape 9 — Actualités et médias

> Statut : **terminée et validée** (24/10/2026). 1009 tests réussis, couverture 97 %.

## Actualités

### Circuit de publication

Brouillon → en relecture → programmé / publié → archivé. Le statut ne se modifie plus à la main : il change uniquement par les **boutons du formulaire** de l'administration (ou les actions groupées de la liste), qui vérifient le rôle côté serveur et tracent la relecture (relu par, relu le).

| Action | Qui | Depuis |
|---|---|---|
| Soumettre en relecture | l'auteur (rédacteur), ou une personne habilitée à publier | brouillon (titre et contenu obligatoires) |
| Publier ou programmer | responsable communication, administrateur du club, super administrateur | brouillon, relecture, programmé, archivé |
| Renvoyer en brouillon (avec une remarque) | idem | relecture, programmé, publié |
| Archiver | idem | publié, programmé |

- **Programmation** : avec une date de publication future, l'article est « programmé ». Il apparaît sur le site **à son heure exacte**. Toutes les 5 minutes, le cron range ensuite son statut à « publié ».
- **Aperçu** : un lien « Prévisualiser » montre l'article tel qu'il sera publié, quel que soit son statut. Il est réservé à l'équipe éditoriale (connexion obligatoire), jamais indexé, jamais mis en cache. « Nouveau lien d'aperçu » invalide l'ancien.
- **Historique** (django-auditlog) : chaque modification d'un article est enregistrée, champ par champ, avec son auteur. Consultation dans l'administration : *Journal d'audit*.
- Un rédacteur ne modifie que ses brouillons. Il ne peut ni publier, ni forcer un statut (testé, y compris en envoyant le statut directement au formulaire).

### Éditeur riche et sécurité

- Éditeur dans l'administration (django-prose-editor, hébergé sur le site) : gras, italique, souligné, barré, intertitres de niveau 2 et 3, listes, citations, séparateurs, liens. Utilisé pour les **articles** et les **pages du club**.
- **Assainissement du HTML (nh3)**, à l'enregistrement **et** à l'affichage : seules les balises de l'éditeur sont conservées. Scripts, styles, cadres, formulaires, attributs `on…`, liens `javascript:` ou `data:` sont retirés. Les liens reçoivent `rel="noopener noreferrer"`. **12 attaques connues** sont testées.
- Un ancien texte saisi sans mise en forme garde ses paragraphes.

### Pages publiques

| Adresse | Contenu |
|---|---|
| `/actualites/` | Articles visibles, 12 par page, **recherche** (titre, chapeau, contenu ; sans tenir compte des majuscules ni des accents) et filtres par catégorie, type et mot-clé |
| `/actualites/<article>/` | Image principale (WebP), contenu, match et joueurs cités (jamais un mineur sans consentement), mots-clés, galerie liée, **partage** Facebook, WhatsApp, X et LinkedIn (simples liens, sans script ni traceur), « À lire aussi », Schema.org `NewsArticle` |

## Médias

| Adresse | Contenu |
|---|---|
| `/medias/` | Vidéos et albums publiés (une date de publication future les masque), filtre par type |
| `/medias/albums/<album>/` | Grille de vignettes ; **visionneuse** (précédente, suivante, flèches du clavier). Sans JavaScript, chaque vignette ouvre la photo en grand |
| `/medias/videos/<vidéo>/` | Lecteur intégré (YouTube en mode « sans cookie », Vimeo, Dailymotion), Schema.org `VideoObject` |

- **Déclinaisons WebP automatiques** (django-imagekit) : vignette 400 × 300, moyenne 1024 px, grande 1920 px (jamais agrandies), couverture d'article 800 × 450 et 1600 px. Elles sont générées au premier affichage puis conservées dans `media/CACHE/`.
- **Envoi groupé** : dans un album, « Ajouter des photos » accepte une sélection multiple (50 au plus). Chaque fichier est vérifié, et un fichier invalide est signalé par son nom sans qu'aucune photo ne soit ajoutée.

### Démonstration

`python manage.py demo_news` crée 9 articles marqués « démo », dans **tous les statuts** : 5 publiés (compte rendu à la une, avant-match, communiqué, interview, mercato), 1 programmé dans 3 jours, 1 en relecture, 1 brouillon, 1 archivé. Ils ont une image principale, une mise en forme variée, des catégories et des mots-clés, et sont reliés à l'album, au match et aux joueurs de démonstration s'ils existent. La commande crée aussi **deux comptes** pour essayer le circuit par rôle, avec le mot de passe affiché par la commande : `redacteur@demo.precisfc.test` (Rédacteur) et `communication@demo.precisfc.test` (Responsable communication). `--delete` supprime articles, catégories, mots-clés, images et comptes de démonstration.

`python manage.py demo_media` crée 2 albums publiés (8 et 6 photos provisoires en 1600 × 1200, aux couleurs variées, pour voir les déclinaisons WebP et la visionneuse) et 3 vidéos réelles en licence libre de la Blender Foundation : *Big Buck Bunny* et *Sintel* sur YouTube, *Big Buck Bunny* sur Vimeo. Leur présence en ligne a été vérifiée. `--delete` supprime ces albums et vidéos ainsi que leurs fichiers, sans toucher au reste. Réservée au développement.

## Validation des images envoyées (tout le site)

Les **26 champs image** du projet (photos, logos, couvertures, avatars…) vérifient désormais chaque envoi :

- **poids** : 8 Mo au plus (réglable par `MAX_UPLOAD_SIZE_MB`) ;
- **extension** : JPEG, PNG, WebP ou GIF ;
- **contenu réel**, lu par Pillow : un fichier renommé en `.jpg` (par exemple un script PHP) est refusé, de même qu'une extension qui ment sur le format ;
- **dimensions** : 40 mégapixels au plus, contre les « bombes de décompression ».

Un test vérifie qu'aucun champ image du projet n'échappe à cette validation.

## Problèmes détectés et corrigés

| Problème | Correction |
|---|---|
| Un ancien texte brut s'affichait avec ses balises `<p>` visibles (double échappement) | Texte échappé puis marqué sûr |
| **Images rognées dans les cartes étroites** (signalé pendant la démonstration : titre coupé sur une couverture d'article) : l'attribut `height` de `<img>` imposait une hauteur fixe, la proportion était ignorée | `height: auto` sur les images des cartes (articles, albums, joueurs) ; un test le vérifie |
| Une image recréée sous le même nom gardait ses anciennes déclinaisons WebP en cache | Les commandes de démonstration suppriment aussi les déclinaisons |
| Le test de l'étape 7 vérifiait qu'un `<script>` était affiché comme texte : il est désormais **supprimé** | Test mis à jour (comportement plus sûr) |

## Vérifications et résultats

| Contrôle | Résultat |
|---|---|
| `ruff check` / `ruff format --check` | Aucun problème |
| `makemigrations --check` | Aucune migration du projet. Seules les tables d'auditlog s'ajoutent, par `migrate` |
| `check --deploy` (production) | Uniquement `security.W004` (HSTS), volontaire |
| `collectstatic` en production | 419 fichiers (éditeur compris) |
| `pytest --cov` | **1009 réussis**, couverture **97 %** |

## Tests ajoutés (95)

- **Circuit de publication (21)** : chaque transition par rôle (autorisée et refusée), programmation, apparition à l'heure, tâche du cron, renvoi en brouillon, archivage et republication, transitions impossibles, boutons selon le rôle, administration (statut impossible à forcer, publication refusée au rédacteur, historique enregistré avec son auteur), aperçu réservé, renouvellement du lien, actions groupées.
- **Assainissement (18)** : 12 attaques, mise en forme conservée, liens, enregistrement, contenu inséré directement en base.
- **Images (10)** : formats valides, trop lourd, mauvaise extension, faux fichier image, extension mensongère, image géante, fichiers existants non revérifiés, tous les champs validés.
- **Pages (18)** : liste, recherche sans accents, filtres, pagination, article, articles non publiés, mineur non cité, plan du site, médias (vignettes WebP réellement générées aux bonnes dimensions, visionneuse, albums masqués, vidéos, envoi groupé avec rejet d'un faux fichier), menu.
- **Démonstration (9)** : articles dans tous les statuts (seuls les publiés visibles), comptes avec leur rôle et connexion possible, albums et vidéos visibles, pas de doublon (lignes ni fichiers), suppression ciblée, refus hors développement.
- **Gabarits (14)** : les 7 nouveaux gabarits compilent, sans commentaire sur plusieurs lignes.

# Étape 6 — Thème du club, gabarits communs, pages d'erreur

> Statut : **terminée et validée** (22/10/2026). 721 tests réussis, couverture 97 %.

## Ce qui a été mis en place

| Élément | Détail |
|---|---|
| Bibliothèques | Bootstrap 5.3.8, Bootstrap Icons 1.13.2, jQuery 3.7.1, **hébergées sur le site** (`static/vendor/`), sans CDN externe. Téléchargées depuis le registre npm officiel, empreinte sha512 vérifiée |
| Couleurs du club | Feuille de style `/theme.css` générée à partir des **Paramètres du club** : une couleur changée dans l'administration s'applique à tout le site, sans redéploiement. Adresse versionnée (`?v=…`), donc mise en cache un an et rafraîchie à chaque modification |
| Contrastes | Textes et liens lisibles (**WCAG AA, 4,5:1**) en mode clair et sombre, quelles que soient les couleurs choisies : une variante lisible est calculée automatiquement si besoin (`apps/core/colors.py`) |
| Mode sombre | Suit le réglage de l'appareil, avec un bouton clair / sombre mémorisé par cookie. Appliqué avant l'affichage (pas de « flash ») |
| Gabarit commun | `templates/base.html` : en-tête et menu, messages, fil d'Ariane, pied de page (coordonnées, réseaux sociaux), lien « Aller au contenu », focus clavier visible |
| Menu | N'affiche que les rubriques qui existent déjà : il se complète au fil des étapes, sans lien mort |
| Sans JavaScript | Le menu s'affiche déplié ; déconnexion et choix du thème sont de simples formulaires |
| `app.js` | Ajoute le jeton CSRF à toutes les requêtes AJAX (`fetch` et jQuery) ; bascule du thème sans rechargement |
| Pages d'erreur | 400, 403, 404, 500 et « formulaire expiré » (CSRF), aux couleurs du club. La page 500 est **autonome** : elle s'affiche même si la base de données est inaccessible |
| Pages de compte | Connexion, inscription, mot de passe… (allauth) et « Mon compte » dans le thème du site, champs et erreurs au format Bootstrap |
| Accueil | Page provisoire ; la page complète arrive à l'étape 7 |

Aucun style ni script n'est écrit directement dans les pages. Cela prépare la politique de sécurité des contenus (CSP) stricte de l'étape 15.

## Problèmes détectés par les tests et corrigés

| Problème | Correction |
|---|---|
| Sur un fond gris moyen, la couleur « rendue lisible » allait vers le blanc, qui n'atteint pas 4,5:1 | La correction va vers le blanc ou le noir, selon celui qui contraste le plus (au moins 4,58:1 dans tous les cas) |
| Les pages de compte perdaient la carte centrée (conflit de noms de blocs entre allauth et le gabarit du site) | La carte est placée dans un bloc distinct |
| La fabrique de tests créait des utilisateurs dont le mot de passe n'était pas enregistré : leur session était aussitôt invalidée | Utilisation du champ `Password` de factory_boy, qui hache avant l'enregistrement |

## Vérifications et résultats

| Contrôle | Résultat |
|---|---|
| `ruff check` / `ruff format --check` | Aucun problème |
| `makemigrations --check` | Aucune migration manquante |
| `check --deploy` (production) | Uniquement `security.W004` (HSTS), volontaire |
| `collectstatic` en production | 401 fichiers, références réécrites (polices d'icônes comprises) |
| `pytest --cov` | **721 réussis**, couverture **97 %** |

## Tests ajoutés (56)

- **Contrastes** : valeurs de référence WCAG, ajustement en mode clair et sombre, et pour 5 palettes (dont des choix extrêmes : jaune, noir, gris), **chaque texte du thème est vérifié à 4,5:1 minimum**.
- **Gabarit** : langue, lien d'évitement, menu, jeton CSRF, paramètres du club affichés, liens selon le visiteur (anonyme, supporter, équipe), lien d'inscription masqué quand les inscriptions sont fermées, mise en cache des paramètres.
- **Thème** : feuille générée avec les couleurs du club, adresse versionnée, cookie de choix, redirections vers un autre site refusées, protection CSRF.
- **Sans JavaScript** : menu déplié, vrais liens, formulaires.
- **Pages d'erreur** : 403, 404, 500 (sur une vraie erreur, et sans base de données).
- **Fichiers** : toutes les bibliothèques sont servies localement, aucune ressource externe dans les pages.

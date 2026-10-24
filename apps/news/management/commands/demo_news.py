"""Actualités de démonstration, dans tous les statuts du circuit de publication.

    python manage.py demo_news           # crée (ou recrée) la démonstration
    python manage.py demo_news --delete  # la supprime, images et comptes compris

Contenu : 9 articles (5 publiés, 1 programmé, 1 en relecture, 1 brouillon, 1 archivé),
avec image principale, mise en forme, catégories et mots-clés ; deux comptes pour
essayer le circuit par rôle (rédacteur, responsable communication). Si les commandes
demo_media et demo_season ont été lancées, les articles sont reliés à leur album,
match et joueurs.

Tout ce qui est créé a un slug « demo-… » ou une adresse « @demo.precisfc.test ».
"""

from datetime import timedelta
from io import BytesIO

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.accounts import roles
from apps.accounts.models import User
from apps.accounts.roles import assign_role
from apps.core.colors import text_color_for
from apps.core.images import delete_with_versions
from apps.core.management.commands.demo_banners import _font, _printable, _text, wrap_text
from apps.core.models import ClubSettings
from apps.matches.models import Match
from apps.media_library.models import Album
from apps.news.models import Article, Category, Tag
from apps.teams.models import Player

PREFIX = "demo-"
DEMO_DOMAIN = "demo.precisfc.test"
# Mot de passe des comptes de démonstration : local uniquement (commande refusée en production).
DEMO_PASSWORD = "Demo-Precis-2026"  # noqa: S105
WRITER_EMAIL = f"redacteur@{DEMO_DOMAIN}"
EDITOR_EMAIL = f"communication@{DEMO_DOMAIN}"

CATEGORIES = [("demo-matchs", "Matchs (démo)"), ("demo-club", "Vie du club (démo)")]
TAGS = [("demo-equipe-premiere", "Équipe première"), ("demo-academie", "Académie")]

BODY = (
    "<p>{lead}</p>"
    "<h2>Les temps forts</h2>"
    "<p>Texte de démonstration : il montre la mise en forme disponible dans l'éditeur, "
    "avec du <strong>gras</strong>, de l'<em>italique</em> et un "
    '<a href="https://precisfc.com">lien</a>.</p>'
    "<ul><li>Premier point important</li><li>Deuxième point</li><li>Troisième point</li></ul>"
    "<blockquote>« Une citation mise en valeur, par exemple celle d'un joueur. »</blockquote>"
    "<h3>Et maintenant ?</h3>"
    "<p>Le prochain rendez-vous est déjà fixé. Rendez-vous au stade !</p>"
)

# (slug, titre, type, statut, décalage de publication en jours, catégorie, à la une, chapeau)
ARTICLES = [
    ("demo-victoire-a-domicile", "Precis FC s'impose 2-0 à domicile (démo)", "MATCH_REPORT",
     "PUBLISHED", -1, "demo-matchs", True, "Une victoire nette devant un public nombreux."),
    ("demo-avant-match-bouake", "Avant-match : déplacement à Bouaké (démo)", "MATCH_PREVIEW",
     "PUBLISHED", -2, "demo-matchs", False, "Tout savoir avant le prochain match."),
    ("demo-horaires-boutique", "Communiqué : nouveaux horaires de la boutique (démo)", "OFFICIAL",
     "PUBLISHED", -4, "demo-club", False, "La boutique du club change d'horaires."),
    ("demo-interview-capitaine", "Interview : trois questions à notre capitaine (démo)",
     "INTERVIEW", "PUBLISHED", -6, "demo-club", False, "Le capitaine fait le point sur la saison."),
    ("demo-mercato-attaquant", "Mercato : un attaquant rejoint le club (démo)", "TRANSFER",
     "PUBLISHED", -8, "demo-club", False, "Un renfort offensif pour la suite de la saison."),
    ("demo-journee-detection", "Académie : journée de détection (démo, programmé)", "ACADEMY",
     "SCHEDULED", 3, "demo-club", False, "Article programmé : visible dans 3 jours."),
    ("demo-partenariat", "Partenariat renouvelé (démo, en relecture)", "PARTNER",
     "IN_REVIEW", None, "demo-club", False, "Article soumis par le rédacteur, à relire."),
    ("demo-soiree-supporters", "Soirée des supporters (démo, brouillon)", "EVENT",
     "DRAFT", None, "demo-club", False, "Brouillon du rédacteur, pas encore soumis."),
    ("demo-ancien-article", "Ancien article archivé (démo)", "NEWS",
     "ARCHIVED", -40, "demo-club", False, "Archivé : n'apparaît plus sur le site."),
]  # fmt: skip


COVER_WIDTH, COVER_HEIGHT = 1600, 900
TITLE_SIZES = (52, 46, 40, 34, 28)  # du plus grand au plus petit
TITLE_MAX_LINES = 3
TITLE_MARGIN, BAND_PADDING = 80, 36


def fit_title(draw, title):
    """Police et lignes du titre : la plus grande taille qui tient en 3 lignes au plus."""
    for size in TITLE_SIZES:
        font, has_accents = _font(size)
        lines = wrap_text(
            draw, _printable(title, has_accents), font, COVER_WIDTH - 2 * TITLE_MARGIN
        )
        if len(lines) <= TITLE_MAX_LINES:
            break
    return font, size, lines


def cover_image(title: str, primary: str, accent: str) -> bytes:
    """Image principale provisoire 1600 × 900 : titre complet dans un bandeau ajusté."""
    image = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), primary)
    draw = ImageDraw.Draw(image)
    font, size, lines = fit_title(draw, title)
    line_height = round(size * 1.3)
    band_top = COVER_HEIGHT - len(lines) * line_height - 2 * BAND_PADDING
    draw.rectangle([(0, band_top), (COVER_WIDTH, COVER_HEIGHT)], fill=accent)
    _text(
        draw, (COVER_WIDTH // 2, band_top // 2), "IMAGE PROVISOIRE", 96, fill="#FFFFFF", anchor="mm"
    )
    text_color = text_color_for(accent)  # noir ou blanc : le plus lisible sur le bandeau
    for number, line in enumerate(lines):
        y = band_top + BAND_PADDING + number * line_height + line_height // 2
        draw.text((COVER_WIDTH // 2, y), line, font=font, fill=text_color, anchor="mm")
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Crée (ou supprime avec --delete) des actualités et des comptes de démonstration."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Supprime la démonstration.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Autorise l'exécution hors développement (comptes au mot de passe connu !).",
        )

    def handle(self, *args, delete=False, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError(
                "Commande de démonstration : réservée au développement (DEBUG). "
                "Ajouter --force pour l'exécuter quand même."
            )
        self.delete_demo()
        if delete:
            self.stdout.write(self.style.SUCCESS("Actualités de démonstration supprimées."))
            return
        call_command("setup_roles", verbosity=0)  # les rôles doivent exister avec leurs droits
        self.create_demo()
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(ARTICLES)} articles de démonstration prêts : /actualites/\n"
                f"Comptes (administration), mot de passe « {DEMO_PASSWORD} » :\n"
                f"  - {WRITER_EMAIL} (Rédacteur)\n"
                f"  - {EDITOR_EMAIL} (Responsable communication)"
            )
        )

    @transaction.atomic
    def delete_demo(self):
        for article in Article.objects.filter(slug__startswith=PREFIX):
            delete_with_versions(article, "cover_image", "cover_card", "cover_wide")
            article.delete()
        Category.objects.filter(slug__startswith=PREFIX).delete()
        Tag.objects.filter(slug__startswith=PREFIX).delete()
        User.objects.filter(email__endswith=f"@{DEMO_DOMAIN}").delete()

    def demo_user(self, email, role, first_name):
        user = User.objects.create_user(email, password=DEMO_PASSWORD, first_name=first_name)
        assign_role(user, role)
        # Adresse vérifiée : connexion possible aussi par le site (allauth).
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        return user

    @transaction.atomic
    def create_demo(self):
        club = ClubSettings.cached()
        now = timezone.now()
        writer = self.demo_user(WRITER_EMAIL, roles.WRITER, "Rédacteur (démo)")
        editor = self.demo_user(EDITOR_EMAIL, roles.COMMUNICATION, "Communication (démo)")
        categories = {
            slug: Category.objects.create(slug=slug, name=name) for slug, name in CATEGORIES
        }
        tags = [Tag.objects.create(slug=slug, name=name) for slug, name in TAGS]
        album = Album.objects.filter(slug__startswith=PREFIX, is_published=True).first()
        match = (
            Match.objects.filter(
                competition_season__season__slug__startswith=PREFIX, status="FINISHED"
            )
            .own_club()
            .order_by("-kickoff_at")
            .first()
        )
        players = list(Player.objects.public().filter(slug__startswith=PREFIX)[:2])

        for slug, title, kind, status, days, category, featured, excerpt in ARTICLES:
            in_workflow = status in ("DRAFT", "IN_REVIEW")
            article = Article(
                slug=slug,
                title=title,
                kind=kind,
                status=status,
                excerpt=excerpt,
                body=BODY.format(lead=excerpt),
                category=categories[category],
                is_featured=featured,
                author=writer if in_workflow else editor,
                publish_at=None if days is None else now + timedelta(days=days),
                reviewed_by=None if in_workflow else editor,
                reviewed_at=None if in_workflow else now,
                cover_alt=f"Illustration : {title}",
            )
            if kind == "MATCH_REPORT":
                article.gallery, article.related_match = album, match
            article.cover_image.save(
                f"{slug}.jpg",
                ContentFile(cover_image(title, club.color_primary, club.color_secondary)),
                save=False,
            )
            article.save()
            article.tags.set(tags if kind in ("MATCH_REPORT", "ACADEMY") else tags[:1])
            if kind == "INTERVIEW":
                article.related_players.set(players)
            self.stdout.write(f"{article.get_status_display()} : {title}")

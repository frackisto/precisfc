"""Saison de démonstration complète, pour voir les pages sportives avec des données.

    python manage.py demo_season           # crée (ou recrée) la saison de démonstration
    python manage.py demo_season --delete  # la supprime

Contenu : 8 clubs fictifs (dont le nôtre), un championnat en matchs aller, les 5 premières
journées jouées (scores, compositions, buts, passes, cartons, remplacements), les
suivantes à venir, et un effectif de 20 joueurs. Deux joueurs sont mineurs : l'un sans
consentement (masqué partout sur le site), l'autre avec (année de naissance seule).

Tout ce qui est créé porte un slug commençant par « demo- » : la suppression ne touche
rien d'autre (notre club existant est réutilisé et conservé).
"""

import random
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.competitions.models import Club, Competition, CompetitionSeason, Participation, Season
from apps.competitions.services.recompute import recompute_edition, recompute_suspended
from apps.core.utils import years_ago
from apps.matches.models import LineupEntry, Match, MatchEvent, MatchTeamStat
from apps.teams.models import Player, Team

PREFIX = "demo-"
OPPONENTS = [
    "Étoile de Cocody",
    "AS Yopougon",
    "Racing Treichville",
    "Olympique de Bouaké",
    "US Korhogo",
    "Lagunes FC",
    "Sporting San-Pédro",
]
SQUAD = [
    # (prénom, nom, poste, numéro)
    ("Ange", "Kouadio", "GK", 1),
    ("Brice", "Tanoh", "GK", 16),
    ("Serge", "Aka", "DF", 2),
    ("Jean-Marc", "Gnagne", "DF", 4),
    ("Hervé", "Yapi", "DF", 5),
    ("Didier", "Koné", "DF", 3),
    ("Arnaud", "Bamba", "DF", 22),
    ("Franck", "Ouattara", "DF", 13),
    ("Junior", "Diabaté", "MF", 6),
    ("Cédric", "Kouamé", "MF", 8),
    ("Wilfried", "Doumbia", "MF", 10),
    ("Hamed", "Traoré", "MF", 14),
    ("Lassina", "Coulibaly", "MF", 17),
    ("Rodrigue", "Assi", "MF", 18),
    ("Sékou", "Fofana", "FW", 7),
    ("Ibrahim", "Cissé", "FW", 9),
    ("Christian", "Yao", "FW", 11),
    ("Moussa", "Sanogo", "FW", 19),
]
MINORS = [
    # Mineur sans consentement : n'apparaît nulle part sur le site public.
    ("Karim", "Protégé", "MF", 30, False),
    # Mineur avec consentement : visible, année de naissance seule.
    ("Abdoul", "Espoir", "FW", 29, True),
]
PLAYED_ROUNDS = 5
KICKOFF = time(16, 0)


def round_robin(teams):
    """Calendrier « chacun contre chacun » (méthode du cercle) : liste de journées."""
    teams = list(teams)
    rounds = []
    for round_number in range(len(teams) - 1):
        pairs = []
        for index in range(len(teams) // 2):
            home, away = teams[index], teams[-1 - index]
            pairs.append((home, away) if round_number % 2 == 0 else (away, home))
        rounds.append(pairs)
        teams = [teams[0], teams[-1], *teams[1:-1]]
    return rounds


class Command(BaseCommand):
    help = "Crée (ou supprime avec --delete) une saison de démonstration complète."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Supprime la démonstration.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Autorise l'exécution hors développement (les données seraient publiques).",
        )

    def handle(self, *args, delete=False, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError(
                "Commande de démonstration : réservée au développement (DEBUG). "
                "Ajouter --force pour l'exécuter quand même."
            )
        self.delete_demo()
        if delete:
            self.stdout.write(self.style.SUCCESS("Saison de démonstration supprimée."))
            return
        edition = self.create_demo()
        recompute_edition(edition.pk)
        self.stdout.write(
            self.style.SUCCESS(
                f"Saison de démonstration prête : {edition.competition.name} {edition.season.name}."
                f" Voir {edition.get_absolute_url()} et /matchs/."
            )
        )

    # --- Suppression ---------------------------------------------------------------

    @transaction.atomic
    def delete_demo(self):
        with recompute_suspended():
            Match.objects.filter(competition_season__season__slug__startswith=PREFIX).delete()
            CompetitionSeason.objects.filter(season__slug__startswith=PREFIX).delete()
            Competition.objects.filter(slug__startswith=PREFIX).delete()
            Player.objects.filter(slug__startswith=PREFIX).delete()
            Team.objects.filter(slug__startswith=PREFIX).delete()
            Club.objects.filter(slug__startswith=PREFIX).delete()
            Season.objects.filter(slug__startswith=PREFIX).delete()

    # --- Création --------------------------------------------------------------------

    @transaction.atomic
    def create_demo(self):
        rng = random.Random(2026)  # noqa: S311  (données fictives reproductibles, pas de sécurité)
        today = timezone.localdate()
        with recompute_suspended():
            season = Season.objects.create(
                name="Démo",
                slug=f"{PREFIX}saison",
                start_date=today - timedelta(weeks=PLAYED_ROUNDS + 2),
                end_date=today + timedelta(weeks=40),
                is_current=True,
            )
            competition = Competition.objects.create(
                name="Championnat (démo)", slug=f"{PREFIX}championnat", kind=Competition.Kind.LEAGUE
            )
            team = Team.objects.create(
                name="Équipe première (démo)",
                slug=f"{PREFIX}equipe-premiere",
                category=Team.Category.FIRST,
                season=season,
            )
            edition = CompetitionSeason.objects.create(
                competition=competition, season=season, team=team
            )
            own_club = Club.objects.filter(is_own_club=True).first() or Club.objects.create(
                name="Precis FC", slug=f"{PREFIX}precis-fc", is_own_club=True
            )
            clubs = [own_club] + [
                Club.objects.create(name=name, slug=f"{PREFIX}{index}-club")
                for index, name in enumerate(OPPONENTS, start=1)
            ]
            for club in clubs:
                Participation.objects.create(competition_season=edition, club=club)
            squad = self.create_squad(team)
            self.create_matches(rng, edition, clubs, own_club, squad, today)
        return edition

    def create_squad(self, team):
        players = []
        for number, (first, last, position, shirt) in enumerate(SQUAD):
            players.append(
                Player.objects.create(
                    team=team,
                    slug=PREFIX + slugify(f"{first} {last}"),
                    first_name=first,
                    last_name=last,
                    position=position,
                    shirt_number=shirt,
                    nationality="CI",
                    birth_date=years_ago(20 + number % 12),
                    height_cm=170 + number % 20,
                    weight_kg=65 + number % 15,
                    is_featured=shirt in (10, 9, 1),
                )
            )
        for first, last, position, shirt, consent in MINORS:
            players.append(
                Player.objects.create(
                    team=team,
                    slug=PREFIX + slugify(f"{first} {last}"),
                    first_name=first,
                    last_name=last,
                    position=position,
                    shirt_number=shirt,
                    nationality="CI",
                    birth_date=years_ago(16),
                    publication_consent=consent,
                    consent_by="Représentant légal (démo)" if consent else "",
                    consent_date=timezone.localdate() if consent else None,
                )
            )
        return players

    def create_matches(self, rng, edition, clubs, own_club, squad, today):
        first_saturday = today - timedelta(days=(today.weekday() - 5) % 7, weeks=PLAYED_ROUNDS - 1)
        for number, pairs in enumerate(round_robin(clubs), start=1):
            day = first_saturday + timedelta(weeks=number - 1)
            kickoff = timezone.make_aware(datetime.combine(day, KICKOFF))
            played = number <= PLAYED_ROUNDS
            for home, away in pairs:
                home_score, away_score = (
                    self.score(rng, home, away, own_club) if played else (None, None)
                )
                match = Match.objects.create(
                    competition_season=edition,
                    matchday=number,
                    home_club=home,
                    away_club=away,
                    kickoff_at=kickoff,
                    venue_name=f"Stade de {home.name}",
                    status=Match.Status.FINISHED if played else Match.Status.SCHEDULED,
                    home_score=home_score,
                    away_score=away_score,
                    attendance=rng.randrange(1500, 9000, 50) if played else None,
                )
                if played and own_club in (home, away):
                    self.create_match_sheet(rng, match, own_club, squad)

    @staticmethod
    def score(rng, home, away, own_club):
        """Scores plausibles, un peu favorables à notre club (c'est sa vitrine)."""
        strong, weak = [1, 2, 2, 3, 3], [0, 0, 1, 1, 2]
        if own_club == home:
            return rng.choice(strong), rng.choice(weak)
        if own_club == away:
            return rng.choice(weak), rng.choice(strong)
        return rng.choice([0, 1, 1, 2, 3]), rng.choice([0, 1, 1, 2])

    @staticmethod
    def pick_scorer(rng, players):
        """Buteur tiré au sort, surtout parmi les attaquants et les milieux."""
        weights = {"FW": 6, "MF": 3, "DF": 1, "GK": 0}
        return rng.choices(players, weights=[weights[player.position] for player in players])[0]

    def create_match_sheet(self, rng, match, own_club, squad):
        own_side = "HOME" if match.home_club == own_club else "AWAY"
        other_side = "AWAY" if own_side == "HOME" else "HOME"
        own_score = match.home_score if own_side == "HOME" else match.away_score
        other_score = match.away_score if own_side == "HOME" else match.home_score

        keepers = [player for player in squad if player.position == "GK"]
        outfield = [player for player in squad if player.position != "GK"]
        starters = [keepers[0], *rng.sample(outfield[: len(SQUAD) - 2], 10)]
        bench = [player for player in outfield if player not in starters][:5]
        for order, player in enumerate(starters):
            LineupEntry.objects.create(
                match=match,
                side=own_side,
                player=player,
                shirt_number=player.shirt_number,
                position=player.get_position_display(),
                is_starter=True,
                is_captain=order == 1,
                order=order,
            )
        for order, player in enumerate(bench, start=11):
            LineupEntry.objects.create(
                match=match, side=own_side, player=player, shirt_number=player.shirt_number,
                is_starter=False, order=order,
            )  # fmt: skip

        on_pitch = list(starters)
        for minute, sub in zip((60, 72), bench[:2], strict=True):
            leaving = rng.choice(on_pitch[1:])
            on_pitch[on_pitch.index(leaving)] = sub
            self.event(match, own_side, minute, "SUBSTITUTION", player=sub, player_out=leaving)

        for _ in range(own_score):
            scorer = self.pick_scorer(rng, on_pitch[1:])
            passer = rng.choice([player for player in on_pitch[1:] if player != scorer])
            self.event(
                match, own_side, rng.randint(5, 90), rng.choice(["GOAL"] * 5 + ["PENALTY_GOAL"]),
                player=scorer, assist_player=passer if rng.random() < 0.7 else None,
            )  # fmt: skip
        for _ in range(other_score):
            self.event(match, other_side, rng.randint(5, 90), "GOAL", player_name="Joueur adverse")
        if rng.random() < 0.8:
            self.event(
                match, own_side, rng.randint(20, 85), "YELLOW", player=rng.choice(on_pitch[1:])
            )

        for side, score in ((own_side, own_score), (other_side, other_score)):
            shots = score + rng.randint(4, 10)
            MatchTeamStat.objects.create(
                match=match,
                side=side,
                possession=55 if side == own_side else 45,
                shots=shots,
                shots_on_target=min(shots, score + rng.randint(1, 4)),
                corners=rng.randint(2, 8),
                fouls=rng.randint(8, 16),
            )

    @staticmethod
    def event(match, side, minute, kind, player=None, **extra):
        MatchEvent.objects.create(
            match=match, side=side, minute=minute, kind=kind, player=player, **extra
        )

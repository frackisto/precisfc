"""Tableau de bord du club (/gestion/).

Accès : personnes connectées ayant un rôle interne (permission ``core.view_dashboard``).
Chaque page ajoute sa propre permission ; tout est vérifié côté serveur. Les pages ne
sont jamais mises en cache ni indexées.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import can_change_match, require
from apps.accounts.roles import DASHBOARD, FINANCIAL_REPORTS
from apps.competitions.models import Season

from . import indicators
from .exports import payments_csv
from .forms import PeriodForm, ScoreForm, period_presets
from .sections import overview, shortcuts, tasks, visible_sections

NAV = [
    ("Accueil", "dashboard:home", DASHBOARD, "speedometer2"),
    ("Finances", "dashboard:finances", FINANCIAL_REPORTS, "graph-up-arrow"),
    ("Scores", "dashboard:scores", "matches.change_match", "123"),
]


def dashboard_view(*perms):
    """Connexion obligatoire, puis rôle interne et permissions de la page (sinon 403)."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            require(request.user.has_perms((DASHBOARD, *perms)))
            return view(request, *args, **kwargs)

        return never_cache(login_required(wrapped))

    return decorator


def dashboard_nav(request):
    current = request.resolver_match.view_name
    return [
        {"label": label, "url": reverse(name), "icon": icon, "active": current == name}
        for label, name, perm, icon in NAV
        if request.user.has_perm(perm)
    ]


def render_dashboard(request, template, context, status=200):
    context = {"dashboard_nav": dashboard_nav(request), **context}
    response = render(request, template, context, status=status)
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def revenue_chart(rows) -> dict:
    return {
        "labels": [f"{row['month']:%m/%Y}" for row in rows],
        "series": [
            {"label": "Boutique", "values": [int(row["shop"]) for row in rows]},
            {"label": "Billetterie", "values": [int(row["ticketing"]) for row in rows]},
        ],
    }


@require_GET
@dashboard_view()
def home(request):
    user = request.user
    now = timezone.now()
    today = timezone.localdate(now)
    month = indicators.this_month(today)
    sections = visible_sections(user)
    season = Season.current() if "sport" in sections else None
    context = {
        "sections": sections,
        "overview": overview(user, season=season, now=now),
        "tasks": tasks(user, now),
        "shortcuts": shortcuts(user),
        "month": month,
        "season": season,
    }
    if "finances" in sections:
        monthly = indicators.revenue_by_month(today)
        context |= {
            "revenue_month": indicators.revenue(month),
            "revenue_year": indicators.revenue(indicators.this_year(today)),
            "pending_payments": indicators.pending_manual_payments(),
            "revenue_rows": monthly,
            "revenue_chart": revenue_chart(monthly),
        }
    if "shop" in sections:
        context |= {
            "orders": indicators.orders_overview(),
            "open_returns": indicators.open_returns_count(),
            "best_sellers": indicators.best_sellers(month),
        }
    if "stock" in sections:
        context["low_stock"] = list(indicators.low_stock_variants()[:50])
    if "ticketing" in sections:
        context |= {
            "ticket_sales": indicators.ticket_sales(now),
            "pending_bookings": indicators.pending_bookings_count(now),
        }
    if "sport" in sections:
        context |= {
            "record": indicators.season_record(season),
            "standings": list(indicators.own_standings(season)),
            "upcoming": list(indicators.upcoming_own_matches(now)),
            "results": list(indicators.last_results()),
        }
    if "news" in sections:
        context["articles"] = indicators.article_counts(user, today)
    if "media" in sections:
        context["media"] = indicators.media_counts()
    if "supporters" in sections:
        context["supporters"] = indicators.supporter_counts(month)
    if "newsletter" in sections:
        context["subscribers"] = indicators.newsletter_subscribers_count()
    if "contact" in sections:
        context["contact"] = indicators.contact_counts()
    if "academy" in sections:
        context["applications"] = indicators.application_counts(today)
    return render_dashboard(request, "dashboard/home.html", context)


@require_GET
@dashboard_view(FINANCIAL_REPORTS)
def finances(request):
    form = PeriodForm(request.GET or None)
    period = form.period
    if not form.is_bound:
        form = PeriodForm(initial={"du": period.first, "au": period.last})
    monthly = indicators.revenue_by_month()
    by_method = indicators.revenue_by_method(period)
    payments = list(indicators.payments_in(period))
    context = {
        "form": form,
        "period": period,
        "presets": period_presets(),
        "revenue": indicators.revenue(period),
        "pending_payments": indicators.pending_manual_payments(),
        "by_method": by_method,
        "method_chart": {
            "labels": [row["label"] for row in by_method],
            "series": [{"label": "Montant", "values": [int(row["amount"]) for row in by_method]}],
        },
        "revenue_rows": monthly,
        "revenue_chart": revenue_chart(monthly),
        "payments": payments,
        "export_query": request.GET.urlencode() if form.is_bound and form.is_valid() else "",
    }
    return render_dashboard(request, "dashboard/finances.html", context)


@require_GET
@dashboard_view(FINANCIAL_REPORTS)
def finances_export(request):
    form = PeriodForm(request.GET or None)
    if form.is_bound and not form.is_valid():
        messages.error(request, "Période invalide : l'export n'a pas été produit.")
        return redirect("dashboard:finances")
    period = form.period
    return payments_csv(indicators.payments_in(period), period)


def score_rows(request, now, bound=None):
    """Lignes de la page des scores : un formulaire par match (celui qui vient d'être
    envoyé garde sa saisie et ses erreurs)."""

    def row(match):
        form = bound if bound is not None and bound.instance.pk == match.pk else None
        return {"match": match, "form": form or ScoreForm(instance=match)}

    awaiting = [row(match) for match in indicators.matches_awaiting_score(request.user, now)]
    recent = [row(match) for match in indicators.recently_finished(request.user, now)]
    return awaiting, recent


@require_GET
@dashboard_view("matches.change_match")
def scores(request):
    awaiting, recent = score_rows(request, timezone.now())
    return render_dashboard(
        request, "dashboard/scores.html", {"awaiting": awaiting, "recent": recent}
    )


@require_POST
@dashboard_view("matches.change_match")
def score_update(request, pk):
    match = get_object_or_404(indicators.scoped_matches(request.user), pk=pk)
    if not can_change_match(request.user, match):
        raise Http404
    form = ScoreForm(request.POST, instance=match)
    if form.is_valid():
        match = form.save(commit=False)
        match.changed_by = request.user
        match.save()
        messages.success(
            request,
            f"Score enregistré : {match.home_club} {match.home_score} - "
            f"{match.away_score} {match.away_club}. Le classement est mis à jour.",
        )
        return redirect("dashboard:scores")
    awaiting, recent = score_rows(request, timezone.now(), bound=form)
    if not any(row["form"] is form for row in awaiting + recent):
        # Match hors des listes (par exemple à venir) : il apparaît en tête avec l'erreur.
        awaiting.insert(0, {"match": match, "form": form})
    messages.error(request, "Le score n'a pas été enregistré : corrigez la saisie.")
    return render_dashboard(
        request, "dashboard/scores.html", {"awaiting": awaiting, "recent": recent}, status=400
    )

from datetime import timedelta

from django import forms
from django.utils import timezone

from apps.matches.models import Match

from . import indicators

# Au-delà, le détail des paiements deviendrait trop long à afficher et à exporter.
MAX_PERIOD_DAYS = 3 * 366


class PeriodForm(forms.Form):
    """Période du rapport financier (dates comprises). Vide : le mois en cours."""

    du = forms.DateField(label="Du", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    au = forms.DateField(label="Au", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cleaned = super().clean()
        today = timezone.localdate()
        default = indicators.this_month(today)
        first = cleaned.get("du") or default.first
        last = cleaned.get("au") or (today if cleaned.get("du") else default.last)
        if last < first:
            raise forms.ValidationError("La date de fin doit suivre la date de début.")
        if (last - first) > timedelta(days=MAX_PERIOD_DAYS):
            raise forms.ValidationError("La période ne peut pas dépasser trois ans.")
        cleaned["period"] = indicators.Period(first, last)
        return cleaned

    @property
    def period(self) -> indicators.Period:
        """Période demandée, ou le mois en cours si la saisie est invalide."""
        if self.is_valid():
            return self.cleaned_data["period"]
        return indicators.this_month()


def period_presets(today=None) -> list[dict]:
    today = today or timezone.localdate()
    presets = [
        ("Ce mois-ci", indicators.this_month(today)),
        ("Le mois dernier", indicators.last_month(today)),
        ("Cette année", indicators.this_year(today)),
        ("12 derniers mois", indicators.last_twelve_months(today)),
    ]
    return [
        {"label": label, "du": period.first.isoformat(), "au": period.last.isoformat()}
        for label, period in presets
    ]


class ScoreForm(forms.ModelForm):
    """Saisie rapide du score : seul le résultat est modifiable ici, le reste de la
    feuille de match (compositions, buteurs…) se complète dans l'administration."""

    status = forms.ChoiceField(
        label="Statut",
        choices=[
            (Match.Status.FINISHED, Match.Status.FINISHED.label),
            (Match.Status.LIVE, Match.Status.LIVE.label),
        ],
        initial=Match.Status.FINISHED,
    )

    class Meta:
        model = Match
        fields = ["home_score", "away_score", "home_penalties", "away_penalties", "status"]
        widgets = {
            name: forms.NumberInput(
                attrs={"min": 0, "max": 99, "class": "form-control score-input"}
            )
            for name in ["home_score", "away_score", "home_penalties", "away_penalties"]
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].widget.attrs["class"] = "form-select"
        for name in ("home_score", "away_score"):
            self.fields[name].required = True
        if self.instance.status not in dict(self.fields["status"].choices):
            self.initial["status"] = Match.Status.FINISHED
        prefix = f"m{self.instance.pk}"
        for name, field in self.fields.items():
            field.widget.attrs["id"] = f"{prefix}-{name}"

    def clean(self):
        cleaned = super().clean()
        for name in ("home_score", "away_score", "home_penalties", "away_penalties"):
            value = cleaned.get(name)
            if value is not None and value > 99:
                self.add_error(name, "Score invalide.")
        return cleaned

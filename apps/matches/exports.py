"""Exports du calendrier : fichier .ics (agendas) et PDF imprimable."""

from datetime import UTC, timedelta
from html import escape
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

MATCH_DURATION = timedelta(hours=2)

# --- iCalendar (RFC 5545) ---------------------------------------------------------------

_BACKSLASH = chr(92)
# Caractères à échapper dans un texte iCalendar (barre oblique inverse en premier).
_ICS_ESCAPES = {
    ord(_BACKSLASH): _BACKSLASH * 2,
    ord(";"): _BACKSLASH + ";",
    ord(","): _BACKSLASH + ",",
    ord("\n"): _BACKSLASH + "n",
    ord("\r"): "",
}


def ics_text(value: str) -> str:
    return str(value).translate(_ICS_ESCAPES)


def fold(line: str) -> str:
    """Lignes de 75 octets au plus, les suivantes commençant par une espace (RFC 5545)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        char_bytes = char.encode("utf-8")
        limit = 75 if not parts else 74
        if len(current) + len(char_bytes) > limit:
            parts.append(current.decode("utf-8"))
            current = b""
        current += char_bytes
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def _utc(value) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def match_title(match) -> str:
    return f"{match.home_club.name} – {match.away_club.name}"


def calendar_ics(matches, *, calendar_name: str, domain: str, url_for) -> str:
    now = _utc(timezone.now())
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Precis FC//Calendrier des matchs//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_text(calendar_name)}",
        "X-WR-TIMEZONE:Africa/Abidjan",
    ]
    for match in matches:
        competition = match.competition_season.competition.name
        venue = match.venue.name if match.venue else match.venue_name
        summary = match_title(match)
        if match.status == match.Status.FINISHED:
            summary += f" ({match.home_score}-{match.away_score})"
        lines += [
            "BEGIN:VEVENT",
            f"UID:match-{match.pk}@{domain}",
            f"DTSTAMP:{now}",
            f"LAST-MODIFIED:{_utc(match.updated_at)}",
            f"DTSTART:{_utc(match.kickoff_at)}",
            f"DTEND:{_utc(match.kickoff_at + MATCH_DURATION)}",
            f"SUMMARY:{ics_text(summary)}",
            f"DESCRIPTION:{ics_text(competition)}",
            f"URL:{url_for(match)}",
            "STATUS:" + ("CANCELLED" if match.status == match.Status.CANCELLED else "CONFIRMED"),
        ]
        if venue:
            lines.append(f"LOCATION:{ics_text(venue)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


# --- PDF -------------------------------------------------------------------------------


def calendar_pdf(matches, *, title: str, club_name: str, primary: str) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=title,
        author=club_name,
    )
    styles = getSampleStyleSheet()
    rows = [["Date", "Heure", "Compétition", "Domicile", "Score", "Extérieur", "Lieu"]]
    for match in matches:
        kickoff = timezone.localtime(match.kickoff_at)
        if match.status == match.Status.FINISHED:
            score = f"{match.home_score} - {match.away_score}"
        else:
            score = {"POSTPONED": "Reporté", "CANCELLED": "Annulé", "LIVE": "En cours"}.get(
                match.status, ""
            )
        rows.append(
            [
                kickoff.strftime("%d/%m/%Y"),
                kickoff.strftime("%H:%M"),
                match.competition_season.competition.name,
                match.home_club.name,
                score,
                match.away_club.name,
                match.venue.name if match.venue else match.venue_name,
            ]
        )
    table = Table(
        rows, repeatRows=1, colWidths=[2.4 * cm, 1.6 * cm, 5 * cm, 5 * cm, 2.2 * cm, 5 * cm, 5 * cm]
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(primary)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (4, 0), (4, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F4F7")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CED4DA")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    generated = timezone.localtime().strftime("%d/%m/%Y à %H:%M")
    story = [
        Paragraph(escape(f"{club_name} — {title}"), styles["Title"]),
        Paragraph(f"Édité le {generated}. Horaires à l'heure d'Abidjan.", styles["Normal"]),
        Spacer(1, 0.5 * cm),
        table if len(rows) > 1 else Paragraph("Aucun match pour ces critères.", styles["Normal"]),
    ]
    document.build(story)
    return buffer.getvalue()

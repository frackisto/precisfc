"""Export CSV des paiements confirmés, lisible directement par Excel ou LibreOffice."""

import csv

from django.http import HttpResponse
from django.utils import timezone

# Marque d'ordre des octets : sans elle, Excel lit le fichier en Windows-1252 et
# déforme les accents.
UTF8_BOM = chr(0xFEFF)
# Une cellule qui commence par l'un de ces caractères serait exécutée comme une formule
# par le tableur (injection de formule) : on la préfixe d'une apostrophe.
FORMULA_PREFIXES = ("=", "+", "-", "@", chr(9), chr(13))

COLUMNS = [
    "Date de confirmation",
    "Identifiant du paiement",
    "Objet",
    "Moyen de paiement",
    "Fournisseur",
    "Référence de la transaction",
    "Montant (FCFA)",
    "Confirmé par",
]


def safe_cell(value) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text


def payment_subject(payment) -> str:
    if payment.order_id:
        return f"Commande {payment.order.number}"
    booking = payment.booking
    return (
        f"Billetterie {booking.reference} ({booking.match.home_club} - {booking.match.away_club})"
    )


def payment_rows(payments):
    for payment in payments:
        yield [
            timezone.localtime(payment.confirmed_at).strftime("%d/%m/%Y %H:%M"),
            str(payment.uuid),
            payment_subject(payment),
            payment.get_method_display(),
            payment.get_provider_display(),
            payment.provider_reference or "",
            f"{payment.amount:.0f}",
            payment.confirmed_by.email if payment.confirmed_by_id else "",
        ]


def payments_csv(payments, period) -> HttpResponse:
    filename = f"paiements-{period.first:%Y%m%d}-{period.last:%Y%m%d}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write(UTF8_BOM)
    # Point-virgule : séparateur attendu par les tableurs réglés en français.
    writer = csv.writer(response, delimiter=";")
    writer.writerow(COLUMNS)
    for row in payment_rows(payments):
        writer.writerow([safe_cell(cell) for cell in row])
    return response

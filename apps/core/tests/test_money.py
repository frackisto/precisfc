"""Montants en francs CFA : sans décimales, groupés par milliers, jamais coupés."""

from decimal import Decimal

import pytest
from django.template import Context, Template

from apps.core.utils import format_fcfa

NBSP = chr(0xA0)


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("15000.00"), f"15{NBSP}000{NBSP}FCFA"),
        (Decimal("0"), f"0{NBSP}FCFA"),
        (Decimal("999"), f"999{NBSP}FCFA"),
        (Decimal("1234567.50"), f"1{NBSP}234{NBSP}568{NBSP}FCFA"),
        (Decimal("1234567.49"), f"1{NBSP}234{NBSP}567{NBSP}FCFA"),
        (17000, f"17{NBSP}000{NBSP}FCFA"),
        ("2500", f"2{NBSP}500{NBSP}FCFA"),
        (None, ""),
        ("", ""),
    ],
)
def test_format_fcfa(amount, expected):
    assert format_fcfa(amount) == expected


def test_template_filters():
    template = Template(
        "{% load money %}{{ a|fcfa }}|{{ n|thousands }}|{{ none|fcfa|default:'—' }}"
    )

    rendered = template.render(Context({"a": Decimal("15000"), "n": 1250, "none": None}))

    assert rendered == f"15{NBSP}000{NBSP}FCFA|1{NBSP}250|—"

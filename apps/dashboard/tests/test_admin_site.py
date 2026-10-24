"""Administration Django aux couleurs du club."""

import pytest
from django.contrib import admin
from django.contrib.staticfiles import finders
from django.urls import reverse

from apps.core.models import ClubSettings
from apps.dashboard.admin_site import APP_ORDER, ClubAdminSite

pytestmark = pytest.mark.django_db

ADMIN = reverse("admin:index")


def test_the_default_admin_site_is_the_club_site():
    assert isinstance(admin.site, ClubAdminSite)


def test_header_and_title_use_the_club_name(login):
    settings_obj = ClubSettings.load()
    settings_obj.name = "Étoile Precis"
    settings_obj.save()

    page = login("superadmin").get(ADMIN).content.decode()

    assert "Étoile Precis — administration" in page
    assert "<title>Administration du site | Administration Étoile Precis</title>" in page


def test_admin_loads_the_club_colours(login):
    page = login("superadmin").get(ADMIN).content.decode()

    assert reverse("core:theme_css") in page
    assert "css/admin.css" in page
    assert finders.find("css/admin.css")


def test_login_page_is_branded_too(client):
    page = client.get(reverse("admin:login")).content.decode()

    assert "administration" in page
    assert "css/admin.css" in page


def test_dashboard_link_in_the_admin(login):
    page = login("writer").get(ADMIN).content.decode()

    assert f'href="{reverse("dashboard:home")}"' in page


def test_apps_follow_the_club_order(login):
    response = login("superadmin").get(ADMIN)

    labels = [app["app_label"] for app in response.context["app_list"]]
    known = [label for label in labels if label in APP_ORDER]
    assert known == sorted(known, key=APP_ORDER.index)
    assert labels[:4] == ["core", "teams", "competitions", "matches"]
    # Les applications non classées (tierces) viennent après.
    assert labels.index("accounts") > labels.index("notifications")


def test_writer_admin_index_only_lists_his_apps(login):
    response = login("writer").get(ADMIN)

    labels = {app["app_label"] for app in response.context["app_list"]}
    assert "news" in labels
    assert "payments" not in labels
    assert "accounts" not in labels


def test_change_form_still_works(login):
    url = reverse("admin:core_clubsettings_change", args=[ClubSettings.load().pk])

    page = login("superadmin").get(url).content.decode()

    assert "css/admin.css" in page
    assert "forms.css" in page


def test_datatables_is_hosted_locally():
    for path in (
        "vendor/datatables/js/dataTables.min.js",
        "vendor/datatables/js/dataTables.bootstrap5.min.js",
        "vendor/datatables/css/dataTables.bootstrap5.min.css",
        "vendor/datatables/LICENSE.txt",
        "js/dashboard.js",
    ):
        assert finders.find(path), path
    with open(finders.find("vendor/datatables/js/dataTables.min.js"), encoding="utf-8") as f:
        assert f.read(30).startswith("/*! DataTables 2.3.8")

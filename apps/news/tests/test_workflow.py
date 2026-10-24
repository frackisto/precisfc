"""Circuit de publication par rôle, programmation, aperçu, historique."""

from datetime import timedelta

import pytest
from auditlog.models import LogEntry
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts import roles
from apps.accounts.roles import assign_role
from apps.news.models import Article
from apps.news.services import workflow
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db
Status = Article.Status


@pytest.fixture(autouse=True)
def setup_roles():
    call_command("setup_roles", verbosity=0)


def user_with(key):
    user = UserFactory()
    assign_role(user, key)
    user.refresh_from_db()
    return user


@pytest.fixture
def writer():
    return user_with(roles.WRITER)


@pytest.fixture
def editor():
    return user_with(roles.COMMUNICATION)


def draft(author, **kwargs):
    values = {"title": "Victoire à domicile", "body": "<p>Belle victoire.</p>", "author": author}
    return Article.objects.create(**{**values, **kwargs})


# --- Transitions par rôle -------------------------------------------------------------------


def test_writer_submits_own_draft_for_review(writer):
    article = workflow.submit_for_review(draft(writer), writer)

    assert article.status == Status.IN_REVIEW


def test_writer_cannot_submit_someone_elses_draft(writer):
    with pytest.raises(PermissionDenied):
        workflow.submit_for_review(draft(UserFactory()), writer)


def test_empty_article_cannot_be_submitted(writer):
    with pytest.raises(workflow.WorkflowError, match="contenu"):
        workflow.submit_for_review(draft(writer, body=""), writer)


def test_writer_can_never_publish(writer):
    article = workflow.submit_for_review(draft(writer), writer)

    with pytest.raises(PermissionDenied):
        workflow.publish(article, writer)
    article.refresh_from_db()
    assert article.status == Status.IN_REVIEW


def test_editor_publishes_and_the_review_is_traced(writer, editor):
    article = workflow.submit_for_review(draft(writer), writer)

    workflow.publish(article, editor)

    article.refresh_from_db()
    assert article.status == Status.PUBLISHED
    assert article.reviewed_by == editor and article.reviewed_at is not None
    assert article.is_visible


def test_future_date_schedules_instead_of_publishing(writer, editor):
    later = timezone.now() + timedelta(days=1)

    article = workflow.publish(draft(writer, publish_at=later), editor)

    assert article.status == Status.SCHEDULED
    assert not article.is_visible
    assert not Article.objects.published().filter(pk=article.pk).exists()


def test_scheduled_article_appears_at_its_time_even_before_the_cron(writer, editor):
    article = workflow.publish(
        draft(writer, publish_at=timezone.now() + timedelta(hours=1)), editor
    )

    in_two_hours = timezone.now() + timedelta(hours=2)
    assert Article.objects.published(in_two_hours).filter(pk=article.pk).exists()


def test_cron_job_marks_due_articles_as_published(writer, editor):
    due = workflow.publish(draft(writer, publish_at=timezone.now() + timedelta(hours=1)), editor)
    later = workflow.publish(
        draft(writer, title="Plus tard", publish_at=timezone.now() + timedelta(days=3)), editor
    )
    Article.objects.filter(pk=due.pk).update(publish_at=timezone.now() - timedelta(minutes=1))

    assert workflow.publish_due_articles() == 1
    due.refresh_from_db()
    later.refresh_from_db()
    assert due.status == Status.PUBLISHED and later.status == Status.SCHEDULED


def test_editor_returns_an_article_to_its_writer_with_a_note(writer, editor):
    article = workflow.submit_for_review(draft(writer), writer)

    workflow.return_to_draft(article, editor, "Ajouter les buteurs.")

    article.refresh_from_db()
    assert article.status == Status.DRAFT and article.review_note == "Ajouter les buteurs."
    workflow.submit_for_review(article, writer)  # le rédacteur peut corriger et resoumettre


def test_archived_article_leaves_the_site_and_can_be_republished(writer, editor):
    article = workflow.publish(draft(writer), editor)

    workflow.archive(article, editor)
    assert not Article.objects.published().filter(pk=article.pk).exists()

    workflow.publish(article, editor)
    assert Article.objects.published().filter(pk=article.pk).exists()


def test_invalid_transitions_are_refused(writer, editor):
    article = workflow.publish(draft(writer), editor)

    with pytest.raises(workflow.WorkflowError):
        workflow.submit_for_review(article, editor)
    with pytest.raises(workflow.WorkflowError):
        workflow.archive(draft(writer), editor)


def test_available_buttons_depend_on_role_and_status(writer, editor):
    article = draft(writer)

    assert [value for value, _ in workflow.available_actions(article, writer)] == ["submit"]
    assert [value for value, _ in workflow.available_actions(article, editor)] == [
        "submit",
        "publish",
    ]
    article.status = Status.PUBLISHED
    assert [value for value, _ in workflow.available_actions(article, editor)] == [
        "return_to_draft",
        "archive",
    ]


# --- Administration ------------------------------------------------------------------------


def admin_post(client, article, action, **fields):
    data = {
        "kind": article.kind,
        "title": article.title,
        "slug": article.slug,
        "excerpt": "",
        "body": article.body,
        "cover_alt": "",
        "meta_title": "",
        "meta_description": "",
        "publish_at_0": "",
        "publish_at_1": "",
        "review_note": "",
        "_workflow": action,
        **fields,
    }
    return client.post(reverse("admin:news_article_change", args=[article.pk]), data)


def test_writer_submits_from_the_admin_and_cannot_force_a_status(client, writer):
    article = draft(writer)
    client.force_login(writer)

    response = admin_post(client, article, "submit", status="PUBLISHED")

    article.refresh_from_db()
    assert response.status_code == 302
    assert article.status == Status.IN_REVIEW


def test_writer_publish_attempt_from_the_admin_is_refused(client, writer):
    article = draft(writer)
    client.force_login(writer)

    admin_post(client, article, "publish")

    article.refresh_from_db()
    assert article.status == Status.DRAFT


def test_editor_publishes_from_the_admin_and_history_is_recorded(client, writer, editor):
    article = workflow.submit_for_review(draft(writer), writer)
    client.force_login(editor)

    admin_post(client, article, "publish", publish_at_0="", publish_at_1="")

    article.refresh_from_db()
    assert article.status == Status.PUBLISHED
    entries = LogEntry.objects.get_for_object(article)
    assert entries.filter(actor=editor).exists()


def test_change_form_shows_the_workflow_buttons(client, writer):
    article = draft(writer)
    client.force_login(writer)

    page = client.get(reverse("admin:news_article_change", args=[article.pk])).content.decode()

    assert 'value="submit"' in page and "Soumettre en relecture" in page
    assert 'value="publish"' not in page


# --- Aperçu ------------------------------------------------------------------------------------


def test_preview_is_reserved_to_the_editorial_team(client, writer):
    article = draft(writer)
    url = reverse("news:preview", args=[article.preview_token])

    assert client.get(url).status_code == 302  # anonyme : vers la connexion
    client.force_login(UserFactory())
    assert client.get(url).status_code == 403  # supporter
    client.force_login(writer)
    page = client.get(url)
    assert page.status_code == 200
    assert (
        "Aperçu" in page.content.decode() and 'content="noindex, nofollow"' in page.content.decode()
    )
    assert "no-cache" in page["Cache-Control"]


def test_renewing_the_preview_link_invalidates_the_old_one(client, writer):
    article = draft(writer)
    old_url = reverse("news:preview", args=[article.preview_token])

    workflow.renew_preview_token(article, writer)

    client.force_login(writer)
    assert client.get(old_url).status_code == 404
    assert client.get(reverse("news:preview", args=[article.preview_token])).status_code == 200


def test_new_preview_link_button_in_the_admin(client, writer):
    article = draft(writer)
    old_token = article.preview_token
    client.force_login(writer)

    response = admin_post(client, article, "renew_preview")

    article.refresh_from_db()
    assert response.status_code == 302
    assert article.preview_token != old_token


def test_bulk_publish_and_archive_from_the_list(client, writer, editor):
    first, second = draft(writer), draft(writer, title="Second article")
    published_one = workflow.publish(draft(writer, title="Déjà publié"), editor)
    client.force_login(editor)
    url = reverse("admin:news_article_changelist")

    client.post(url, {"action": "publish_selected", "_selected_action": [first.pk, second.pk]})
    client.post(
        url, {"action": "archive_selected", "_selected_action": [published_one.pk, first.pk]}
    )

    statuses = dict(Article.objects.values_list("title", "status"))
    assert statuses["Second article"] == Status.PUBLISHED
    assert statuses["Déjà publié"] == Status.ARCHIVED
    assert statuses["Victoire à domicile"] == Status.ARCHIVED


def test_bulk_actions_skip_what_the_user_may_not_do(client, writer):
    article = draft(writer)
    writer.user_permissions.clear()
    client.force_login(writer)

    response = client.post(
        reverse("admin:news_article_changelist"),
        {"action": "publish_selected", "_selected_action": [article.pk]},
        follow=True,
    )

    article.refresh_from_db()
    assert article.status == Status.DRAFT
    assert "Non traités" in response.content.decode()

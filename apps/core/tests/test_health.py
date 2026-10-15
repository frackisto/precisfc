from django.urls import reverse


def test_healthz_returns_ok(client):
    response = client.get(reverse("core:healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "no-cache" in response["Cache-Control"]


def test_healthz_rejects_post(client):
    response = client.post(reverse("core:healthz"))

    assert response.status_code == 405

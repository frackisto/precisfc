from apps.accounts.axes import get_login_email


def test_email_comes_from_allauth_or_admin_credentials():
    assert get_login_email(None, {"email": " Awa@Precisfc.test "}) == "awa@precisfc.test"
    assert (
        get_login_email(None, {"username": "DIRECTION@precisfc.test"}) == "direction@precisfc.test"
    )


def test_email_falls_back_to_the_submitted_form(rf):
    assert get_login_email(rf.post("/", {"login": "Kofi@X.ci"}), None) == "kofi@x.ci"
    assert get_login_email(rf.post("/", {"username": "a@b.ci"}), {}) == "a@b.ci"


def test_missing_email_gives_none(rf):
    assert get_login_email(rf.get("/"), None) is None
    assert get_login_email(None, None) is None

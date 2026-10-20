from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """Inscriptions fermées tant que ``DJANGO_SIGNUP_OPEN`` est faux (voir settings)."""
        return settings.ACCOUNT_SIGNUP_OPEN

"""Identifiant utilisé par django-axes pour compter les échecs de connexion."""


def get_login_email(request, credentials):
    """Adresse e-mail saisie, quel que soit le formulaire.

    allauth transmet ``email``, l'administration ``username`` ; lors du contrôle d'une
    requête, seul le formulaire envoyé (``login`` ou ``username``) est disponible.
    L'adresse est mise en minuscules : « Awa@… » et « awa@… » partagent le même compteur.
    """
    credentials = credentials or {}
    value = credentials.get("email") or credentials.get("username") or credentials.get("login")
    if not value and request is not None:
        value = request.POST.get("login") or request.POST.get("username")
    return (value or "").strip().lower() or None

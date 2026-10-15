"""Point d'entrée ASGI (réservé à la V2 : Django Channels sur VPS)."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()

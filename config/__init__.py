from config.db_driver import install_mysql_driver

MYSQL_DRIVER = install_mysql_driver()

from config.celery import app as celery_app  # noqa: E402

__all__ = ["MYSQL_DRIVER", "celery_app"]

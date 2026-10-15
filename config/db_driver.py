"""Sélection du pilote MySQL/MariaDB.

mysqlclient est le pilote officiel de Django, mais il doit être compilé sous Linux,
ce qui peut échouer sur un hébergement mutualisé. Dans ce cas, PyMySQL (pur Python)
se fait passer pour ``MySQLdb`` et Django l'utilise de façon transparente.
"""


def install_mysql_driver() -> str:
    """Rend un module ``MySQLdb`` importable et renvoie le nom du pilote retenu."""
    try:
        import MySQLdb  # noqa: F401
    except ImportError:
        import pymysql

        pymysql.install_as_MySQLdb()
        return "pymysql"
    return "mysqlclient"

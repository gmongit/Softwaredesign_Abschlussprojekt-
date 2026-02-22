from tinydb import TinyDB


class _DatabaseManager:
    """
    Interner DatabaseManager.
    """
    def __init__(self, db_path="data.json"):
        """
        Initialisiert den DatabaseManager.

        Pfad zur Datenbank-Datei (standart: "data.json")
        """
        self.db_path = db_path
        self._db = None

    def get_db(self):
        """
        Verbindet sich mit Datenbank & gibt Insatanz zurück oder initialisiert eine Neue.

        Returns:
            TinyDB Instanz
        """
        if self._db is None:
            self._db = TinyDB(self.db_path)
        return self._db

    def get_table(self, table_name):
        """
        Greift auf eine spezifische Tabelle in der Datenbank zu.

        Args:
            table_name (str): Der Name der Tabelle, die abgerufen werden soll.

        Returns:
            Table: Ein Tabellen-Objekt für weitere Abfragen.
        """
        return self.get_db().table(table_name)

    def close(self):
        """
        Schließt die Datenbank.
        """
        if self._db is not None:
            self._db.close()
            self._db = None


# Singleton-Instanz
db_manager = _DatabaseManager()
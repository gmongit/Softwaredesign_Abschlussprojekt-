from dataclasses import dataclass
from tinydb import Query
from core.db.database import db_manager


@dataclass(slots=True)
class MaterialMeta:
    """Metadaten für ein gespeichertes Material."""
    name: str
    e_modul: float
    streckgrenze: float
    dichte: float


class MaterialStore:
    """
    Store für Material-Daten.
    Name ist der eindeutige Schlüssel - jedes Material kann nur einmal existieren.
    """

    def __init__(self):
        self.table_name = 'materials'

    def _get_table(self):
        """Gibt Material-Tabelle zurück."""
        return db_manager.get_table(self.table_name)

    def save_material(self, name, e_modul, streckgrenze, dichte):
        """
        Speichert ein Material in der Datenbank.

        Args:
            name: Name des Materials (eindeutiger Schlüssel)
            e_modul: E-Modul in GPa
            streckgrenze: Streckgrenze in MPa
            dichte: Dichte in kg/m³

        Returns:
            name: Der Name des gespeicherten Materials

        Raises:
            ValueError: Wenn Material mit diesem Namen bereits existiert oder Name leer ist
        """
        table = self._get_table()
        Material = Query()

        name = str(name).strip()
        if not name:
            raise ValueError("Material-Name darf nicht leer sein!")

        if table.contains(Material.name == name):
            raise ValueError(f"Material '{name}' existiert bereits! Bitte wähle einen anderen Namen.")

        table.insert({
            "name": name,
            "e_modul": float(e_modul),
            "streckgrenze": float(streckgrenze),
            "dichte": float(dichte),
        })

        return name

    def edit_material(self, old_name, new_name, e_modul, streckgrenze, dichte):
        """
        Bearbeitet ein Material. Wenn der Name gleich bleibt, werden nur die Werte
        aktualisiert. Wenn der Name sich ändert, wird das alte Material gelöscht
        und ein neues mit dem neuen Namen angelegt.

        Args:
            old_name: Aktueller Name des Materials
            new_name: Neuer Name (darf gleich old_name sein)
            e_modul: E-Modul in GPa
            streckgrenze: Streckgrenze in MPa
            dichte: Dichte in kg/m³

        Raises:
            KeyError: Wenn old_name nicht gefunden wurde
            ValueError: Wenn new_name bereits existiert (und != old_name)
        """
        table = self._get_table()
        Material = Query()

        new_name = str(new_name).strip()
        if not new_name:
            raise ValueError("Material-Name darf nicht leer sein!")

        if not table.contains(Material.name == old_name):
            raise KeyError(f"Material '{old_name}' nicht gefunden!")

        if new_name == old_name:
            # Nur Werte aktualisieren
            table.update(
                {
                    'e_modul': float(e_modul),
                    'streckgrenze': float(streckgrenze),
                    'dichte': float(dichte),
                },
                Material.name == old_name
            )
        else:
            # Name hat sich geändert: prüfen ob neuer Name frei ist
            if table.contains(Material.name == new_name):
                raise ValueError(f"Material '{new_name}' existiert bereits!")
            # Altes löschen, neues anlegen
            table.remove(Material.name == old_name)
            table.insert({
                'name': new_name,
                'e_modul': float(e_modul),
                'streckgrenze': float(streckgrenze),
                'dichte': float(dichte),
            })

    def list_materials(self):
        """
        Listet alle gespeicherten Materialien auf.

        Returns:
            Liste von MaterialMeta Objekten, sortiert nach Name
        """
        table = self._get_table()
        docs = table.all()

        metas = []
        for d in docs:
            metas.append(
                MaterialMeta(
                    name=str(d.get("name", "")),
                    e_modul=float(d.get("e_modul", 0.0)),
                    streckgrenze=float(d.get("streckgrenze", 0.0)),
                    dichte=float(d.get("dichte", 0.0)),
                )
            )

        metas.sort(key=lambda m: m.name)
        return metas

    def load_material(self, name):
        """
        Lädt ein Material aus der Datenbank.

        Args:
            name: Name des Materials

        Returns:
            MaterialMeta Objekt

        Raises:
            KeyError: Wenn Material nicht gefunden wurde
        """
        table = self._get_table()
        Material = Query()
        doc = table.get(Material.name == name)

        if doc is None:
            raise KeyError(f"Material '{name}' nicht gefunden!")

        return MaterialMeta(
            name=str(doc.get("name", "")),
            e_modul=float(doc.get("e_modul", 0.0)),
            streckgrenze=float(doc.get("streckgrenze", 0.0)),
            dichte=float(doc.get("dichte", 0.0)),
        )

    def delete_material(self, name):
        """
        Löscht ein Material aus der Datenbank.

        Args:
            name: Name des zu löschenden Materials

        Returns:
            True wenn Material gelöscht wurde, False wenn nicht gefunden
        """
        table = self._get_table()
        Material = Query()
        removed = table.remove(Material.name == name)

        return len(removed) > 0


# Singleton-Instanz
material_store = MaterialStore()
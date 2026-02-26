# 🔧 Topologie-Optimierung – Stabwerk-Analyse

Eine interaktive Web-App zur Topologie-Optimierung von 2D-Fachwerk-Strukturen, entwickelt mit Python und Streamlit.

---

## 📖 Was macht dieses Programm?

Das Programm beantwortet die Frage:  
**„Welche Stäbe eines Tragwerks kann ich entfernen, ohne dass es versagt – bei minimalem Materialeinsatz?"**

Ausgangspunkt ist ein rechteckiges Federgitter (Stabwerk). Der Nutzer definiert die Geometrie, die Lagerung und die Last. Ein energiebasierter Optimierungsalgorithmus entfernt dann schrittweise die am wenigsten belasteten Knoten, bis ein gewünschter Massenanteil erreicht ist.

---

## 🚀 Installation & Start

### Voraussetzungen
- Python 3.10 oder höher
- Git

### Setup

```bash
# Repository klonen
git clone https://github.com/dein-repo/topologie-optimierung.git
cd topologie-optimierung

# Virtuelle Umgebung erstellen und aktivieren
python -m venv .venv
source .venv/Scripts/activate  # Windows (Git Bash)
source .venv/bin/activate       # Mac/Linux

# Abhängigkeiten installieren
pip install -r requirements.txt

# App starten
streamlit run app/main.py
```

---

## 🗂️ Projektstruktur

```
app/
  main.py                        # Einstiegspunkt & Navigation
  plots.py                       # Gemeinsame Plotly-Visualisierungen
  shared.py                      # Gemeinsame UI-Komponenten
  pages/
    Material_Manager.py          # Materialverwaltung
    Structure_Creator.py         # Strukturdefinition & Bearbeitung
    Optimizer.py                 # Statische Optimierung
    Dynamic_Optimizer.py         # Dynamische Optimierung
  service/
    optimization_service.py      # Optimierungslogik
    structure_service.py         # Strukturlogik

core/
  model/
    node.py                      # Knotenmodell
    spring.py                    # Federmodell
    structure.py                 # Gesamtstruktur
    boundary_conditions.py       # Randbedingungen
  optimization/
    optimizer_base.py            # Abstrakte Basisklasse
    energy_based_optimizer.py    # Statischer Optimizer
    dynamic_optimizer.py         # Dynamischer Optimizer
  solver/
    solver.py                    # Hauptsolver
    stiffness_matrix.py          # Steifigkeitsmatrix
    mass_matrix.py               # Massenmatrix
    eigenvalue_solver.py         # Eigenwertlöser
    regularization.py            # Regularisierung
```

---

## 📋 Benutzungsanleitung

### Schritt 1 – Material Manager
Materialien mit Name, E-Modul (GPa), Streckgrenze (MPa) und Dichte (kg/m³) anlegen, bearbeiten und löschen. Die Daten werden persistent in einer TinyDB-Datenbank gespeichert und dienen als Grundlage für die physikalisch korrekte Berechnung der Federsteifigkeiten und Stabmassen.

### Schritt 2 – Strukturdefinition
Strukturen können auf drei Wegen erstellt werden:
- **Manuell** – Rechteckgitter mit wählbarer Auflösung (nx, ny) und Abmessungen
- **Laden** – gespeicherte Cases aus der Datenbank laden
- **Bild hochladen** – Foto (PNG/JPG/BMP/WebP) wird automatisch in eine Gitterstruktur konvertiert

Nach dem Erstellen kann die Struktur interaktiv bearbeitet werden: Knoten ein-/ausschalten, Festlager, Loslager und Lasten per Klick auf beliebige Knoten setzen.

### Schritt 3 – Optimierung
- **Ziel-Massenanteil** einstellen (z.B. 0.4 = 40% des Materials bleibt übrig)
- **Entfernungsrate** und **Max. Iterationen** festlegen
- **Material und Sicherheitsfaktor** wählen
- Auf **„Optimierung starten"** klicken

### Schritt 4 – Ergebnis analysieren

| Ansicht | Beschreibung |
|---|---|
| **Struktur** | Optimiertes Stabwerk mit Randbedingungen |
| **Heatmap** | Federenergien – rot = stark belastet, blau = gering belastet |
| **Lastpfade** | Kraftfluss von der Last zu den Auflagern |
| **Verformung** | Unverformte Referenz + verformte Struktur (skalierbar) |
| **Replay** | Schritt-für-Schritt Animation der Optimierung |

---

## ⚙️ Berechnungsschritte

1. **Aufstellen der globalen Steifigkeitsmatrix**  
   `K = Σ k_e` mit `k_e = E · A / L`

2. **Lösung des linearen Gleichungssystems**  
   `K · u = F`

3. **Berechnung der Formänderungsenergie pro Stab**  
   `E_e = ½ · k_e · (Δu)²`

4. **Entfernen von Knoten mit geringer Energie**  
   Knoten mit dem geringsten Energieanteil werden schrittweise entfernt. Symmetrische Knotenpaare werden gemeinsam entfernt.

5. **Spannungsconstraint**  
   Wird die Streckgrenze (× Sicherheitsfaktor) überschritten, stoppt die Entfernung.

6. **Konnektivitätsprüfung**  
   In jedem Schritt wird sichergestellt, dass Last und Auflager weiterhin verbunden sind.

---

## 🔄 Dynamische Optimierung

Zusätzlich zur statischen Optimierung bietet der **Dynamic Optimizer** eine eigenfrequenzbasierte Optimierung. Über einen Alpha-Parameter lässt sich stufenlos zwischen statischem und dynamischem Kriterium wechseln. Ziel ist die Vermeidung von Resonanz – die Eigenfrequenz der Struktur soll möglichst weit von einer vorgegebenen Anregungsfrequenz entfernt bleiben.

---

## 💾 Export

- **PNG** – jede Ansicht kann als Bild gespeichert werden
- **GIF** – Replay-Animation und Eigenmodus-Oszillation
- **Case speichern** – komplette Struktur inkl. Optimierungshistorie in die Datenbank

---

## 👥 Entwickelt von

MCI – Semester 3, Softwaredesign  
gmongit · Christian Jäschke · nsextro-code 
Studienjahr 2025/2026

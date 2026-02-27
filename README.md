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
git clone https://github.com/gmongit/Softwaredesign_Abschlussprojekt-.git
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
    SIMP_Optimizer.py            # SIMP-Optimierung
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
    simp_optimizer.py            # SIMP-Optimizer
    support_rebuilder.py         # Nachverstärkung nach Überoptimierung
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
Materialien mit Name, E-Modul (GPa), Streckgrenze (MPa) und Dichte (kg/m³) anlegen, bearbeiten und löschen. Die Daten werden persistent in einer TinyDB-Datenbank gespeichert und dienen als Grundlage für die physikalisch korrekte Berechnung der Federsteifigkeiten und Stabmassen & berechnung mit Einbezug der Streckgrenze

### Schritt 2 – Strukturdefinition
Strukturen können auf drei Wegen erstellt werden:
- **Manuell** – Rechteckgitter mit wählbarer Auflösung (nx, ny) und Abmessungen
- **Laden** – gespeicherte Cases aus der Datenbank laden
- **Bild hochladen** – Foto (PNG/JPG/BMP/WebP) wird automatisch in eine Gitterstruktur konvertiert
- **Zeichnen** – Struktur direkt im Browser auf einem Raster freihand zeichnen

Nach dem Erstellen kann die Struktur interaktiv bearbeitet werden: Knoten ein-/ausschalten, Festlager, Loslager und Lasten per Klick auf beliebige Knoten setzen.

### Schritt 3 – Optimierung
- **Ziel-Massenanteil** einstellen (z.B. 0.4 = 40% des Materials bleibt übrig)
- **Entfernungsrate** und **Max. Iterationen** festlegen
- **Material** wählen – Federsteifigkeiten und Stabmassenwerden daraus berechnet
- Optional: **Streckgrenzen-Limit** aktivieren – die Optimierung stoppt dann, sobald die maximale Spannung die Streckgrenze (× Sicherheitsfaktor) überschreitet
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

Der **Dynamic Optimizer** erweitert die statische Optimierung um ein eigenfrequenzbasiertes Kriterium. Ziel ist es, Resonanz zu vermeiden. Die erste Eigenfrequenz der Struktur soll möglichst weit von einer vorgegebenen Anregungsfrequenz entfernt bleiben.

### Berechnungsschritte

1. **Massenmatrix aufstellen**
   Diagonale Massenmatrix (lumped mass): jeder aktive Knoten erhält eine gleichmäßige Masse.

2. **Eigenwertproblem lösen**
   `K · φ = ω² · M · φ`
   Die erste Eigenkreisfrequenz `ω₁` und der erste Eigenvektor `φ₁` werden berechnet.

3. **Dynamische Knotenwichtigkeit**
   Basierend auf dem Rayleigh-Quotienten: Knoten mit hoher Auslenkung im ersten Eigenmode gelten als wichtig für die Eigenfrequenz.

4. **Kombinierter Score**
   `score = (1 - α) · statisch + α · dynamisch`
   Mit `α = 0` rein statisch, mit `α = 1` rein dynamisch.

5. **Entfernung** wie beim statischen Optimizer – Knoten mit dem niedrigsten Score werden zuerst entfernt.

### Parameter

| Parameter | Beschreibung |
|---|---|
| **ω_E [rad/s]** | Anregungsfrequenz, vor der die Struktur geschützt werden soll |
| **α (Alpha)** | Gewichtung: 0 = rein statisch, 1 = rein dynamisch |
| **Ziel-Massenanteil** | Wie viel Material soll übrig bleiben |
| **Knotenmasse** | Fallback-Masse pro Knoten, wenn kein Material hinterlegt ist |

### Ergebnisansichten

| Ansicht | Beschreibung |
|---|---|
| **Struktur** | Optimiertes Stabwerk |
| **Eigenfrequenz-Verlauf** | ω₁ über Iterationen + Markierung der Anregungsfrequenz |
| **Frequenzabstand** | \|ω₁ − ω_E\| pro Iteration – je größer, desto sicherer vor Resonanz |
| **Massenabbau** | Massenanteil über die Iterationen |

---

## 📐 SIMP-Optimierung

Der **SIMP-Optimizer** (Solid Isotropic Material with Penalization) verfolgt einen anderen Ansatz als die knotenbasierte Optimierung: Statt Knoten zu entfernen, werden die **Querschnittsflächen aller Stäbe kontinuierlich angepasst**. Stäbe mit geringer Bedeutung werden durch eine Penalisierung automatisch gegen null gedrängt und am Ende entfernt.

### Berechnungsschritte

1. **SIMP-Penalisierung**
   Die Steifigkeit jedes Stabs wird mit seiner Dichte `ρ = A / A_max` skaliert:
   `k_eff = ρᵖ · k_voll`
   Der Exponent `p > 1` bestraft dünne Stäbe überproportional und drängt die Lösung zu klar definierten „voll" oder „leer" Stäben.

2. **Statische Lösung**
   `K · u = F` — wie beim statischen Optimizer.

3. **Sensitivitäten berechnen**
   Ableitung der Compliance nach der Stabfläche:
   `dc/dA_e = −p · ρ_e^(p−1) · (E/L) · Δu_e²`
   Stäbe mit hoher Sensitivität tragen viel zur Steifigkeit bei und behalten ihre Fläche.

4. **Optimality-Criteria Update (OC)**
   Die neuen Stabflächen werden über einen Lagrange-Multiplikator (Bisektionsverfahren) so berechnet, dass das Zielvolumen eingehalten wird. Ein Move-Limit begrenzt die Änderung pro Iteration.

5. **Nachbearbeitung**
   Stäbe mit einer Fläche unter einem Schwellenwert werden entfernt, sofern die Struktur danach noch lösbar bleibt.

### Parameter

| Parameter | Beschreibung |
|---|---|
| **Ziel-Volumenanteil** | Wie viel Material (Volumen) soll übrig bleiben |
| **Penalisierung p** | Stärke der SIMP-Bestrafung (typisch: 3) – höhere Werte → schärfere Topologie |
| **Move-Limit** | Maximale Änderung der Stabfläche pro Iteration (relativ zu A_max) |
| **Toleranz** | Konvergenzkriterium – Abbruch wenn Compliance- und Flächenänderung < tol |

### Ergebnisansichten

| Ansicht | Beschreibung |
|---|---|
| **Struktur** | Stabwerk mit farblich kodierten Querschnittsflächen |
| **Compliance-Verlauf** | Gesamtsteifigkeit über Iterationen – sollte konvergieren |
| **Volumenanteil** | Materialanteil über die Iterationen |

---

## 🔧 Support Rebuilder

Der **Support Rebuilder** kann manuell aktiviert werden und hilft dabei,  die am stärksten belastete Stelle zu entlasten. Er reaktiviert gezielt zuvor entfernte Knoten, um die Spannungsspitze zu senken, – ohne die gesamte Optimierung zu wiederholen.

- Sucht in der Nachbarschaft der am stärksten belasteten Federn nach deaktivierten Knoten
- Gruppiert Kandidaten in Cluster und testet Kombinationen (Brute-Force mit Limit)
- Reaktiviert nur die Knoten, die die Spannung tatsächlich unter die Streckgrenze senken
- Ergebnis: minimaler Materialzuwachs & Schwachstelle wird gezielt entlastet

Mit folgendem Setup lässt sich der Support Rebuilder gut testen.
Da es vorkommen kann, dass Reaktivierungen nur geringe Verbesserungen bringen oder Spannungsspitzen Global sogar verschlechtern.

Struktur:  Breite: 10 | Höhe: 2 | Knoten (x): 45 | Knoten (y): 32
Optimizer:  Material: Aluminium EN-AW6060 | Streckgrenzen-Limit: deaktiviert | Ziel-Massenanteil: 0.17 | Entfernungsrate: 0.05 | Max. Iterationen: 120
Support Rebuilder:  Top Federn: 20 % | Min. Lastschwelle: 75 % | Min. Verbesserung: 5 %
Ergebnis (Referenzlauf):  Reduktion des maximalen Stresses: 29% | Zusätzliche Masse: 1,1 %

---
### Solver()

Verwendung eines **Sparse-Solvers** von SciPy, zusätzlich wird über LSQR-Fallback und das relative Residuum ||K·u − F|| / ||F|| sichergestellt, dass numerisch unzuverlässige Lösungen – auch bei fast-singulärem Verhalten – erkannt und verworfen werden (None).

---
### Symmetrieerkennung
die Struktur wird automatisch auf vertikale Spiegelsymmetrie geprüft; symmetrische Knotenpaare werden stets gemeinsam entfernt, sodass die Symmetrie über alle Iterationen erhalten bleibt

---

## 💾 Export

- **PNG** – jede Ansicht kann als Bild gespeichert werden
- **GIF** – Replay-Animation und Eigenmodus-Oszillation
- **Case speichern** – komplette Struktur inkl. Optimierungshistorie in die Datenbank

---

## 🤖 Verwendete Hilfsmittel

Zur Unterstützung während der Entwicklung wurde KI-Assistenz (Claude von Anthropic & Google Gemini) eingesetzt. Die KI hat dabei in folgenden Bereichen geholfen:

- **Debugging & Fehlerbehebung** – Analyse von Fehlermeldungen sowie Erkennung und Korrektur von Syntax- und Logikfehlern
- **Versionskontrolle** – Git-Workflows, Branch-Management und Merge-Konflikte
- **Testing** – Strukturierung und Formulierung von Unit-Tests
- **Projektstruktur** – Aufteilung in Module und Schichten (Core / App / Service)
- **Visualisierung** – Verbesserung der UI durch Emojis und Plotly-Diagramme
- **Mathematische Erklärungen** – insbesondere beim SIMP-Optimizer (Sensitivitäten, OC-Update) und beim Dynamic Optimizer (Rayleigh-Quotient, Eigenwertproblem)

Die eigentliche Implementierung, die fachlichen Entscheidungen und das Gesamtkonzept stammen von den Projektmitgliedern.

---

## 👥 Entwickelt von

MCI – Semester 3, Softwaredesign
Simon franz  · Christian Jäschke · Noah Sextro


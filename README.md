# 🔧 Topologie-Optimierung – Stabwerk-Analyse

Eine interaktive Web-App zur Topologie-Optimierung von Stabwerken, entwickelt mit Python und Streamlit.

---

## 📖 Was macht dieses Programm?

Das Programm beantwortet die Frage:  
**„Welche Stäbe eines Tragwerks kann ich entfernen, ohne dass es versagt – bei minimalem Materialeinsatz?"**

Ausgangspunkt ist ein rechteckiges 2D-Stabgitter.
Ein energie­basierter Optimierungsalgorithmus entfernt iterativ schwach belastete Elemente, bis ein gewünschter Massenanteil erreicht ist.

---

## 🚀 Installation & Start

### Voraussetzungen
- Python 3.10 oder höher
- Git

### Setup

```bash
# Repository klonen
git clone https://github.com/gmongit/Softwaredesign_Abschlussprojekt-.git
cd Softwaredesign_Abschlussprojekt-


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

## Physikalisches Modell

Das Tragwerk wird als lineares 2D-Stabwerk modelliert:

- 2 Freiheitsgrade pro Knoten (ux, uy)
- Lineare Elastizität (Hooke)
- Kleine Verformungen
- Axiale Stäbe (keine Biegung)

### Berechnungsschritte

1. Aufstellen der globalen Steifigkeitsmatrix  
   \[
   K = \sum k_e
   \]

2. Lösung des linearen Gleichungssystems  
   \[
   K \cdot u = F
   \]

3. Berechnung der Stabenergie  
   \[
   E_e = \frac{1}{2} k_e (\Delta L)^2
   \]

4. Entfernen von Elementen mit geringer Energie

5. Konnektivitätsprüfung  
   → Sicherstellen, dass Last und Auflager weiterhin verbunden sind



## 📋 Benutzungsanleitung

### Schritt 1 – Material Manager
- Werkstoffe definieren (E-Modul, Streckgrenze, Dichte)
- Gespeicherte Materialien können im Structure Creator verwendet werden

### Schritt 2 – Strukturdefinition
- **Breite & Höhe** des Gitters in Metern eingeben
- **Anzahl der Knoten** in X- und Y-Richtung festlegen (nx, ny)
- **Last Fy** in Newton eingeben (negativer Wert = nach unten)
- Auf **„Struktur erstellen"** klicken
- Die Struktur wird als Einfeldträger erstellt:
  - Loslager unten links (fix Y)
  - Festlager unten rechts (fix X & Y)
  - Last oben Mitte

### Schritt 3 – Optimierung
- **Ziel-Massenanteil** einstellen (z.B. 0.4 = 40% des Materials bleibt übrig)
- **Entfernungsrate** pro Iteration einstellen
- **Max. Iterationen** festlegen
- Auf **„Optimierung starten"** klicken
- Das Ergebnis wird als interaktiver Plot angezeigt

### Ansichten nach der Optimierung
| Ansicht | Beschreibung |
|---|---|
| **Struktur** | Optimiertes Stabwerk |
| **Heatmap** | Federenergien – rot = stark belastet, blau = gering belastet |
| **Lastpfade** | Kraftfluss von der Last zu den Auflagern |

---

## ⚙️ Wie funktioniert der Algorithmus?

1. **Steifigkeitsmatrix** K wird aufgestellt
2. Lineares Gleichungssystem **K · u = F** wird gelöst → Verschiebungen u
3. Für jede Feder wird die **Formänderungsenergie** berechnet
4. Knoten mit geringer Energie (= wenig zur Lastübertragung beitragend) werden entfernt
5. Nach jeder Entfernung wird geprüft ob die Struktur noch **zusammenhängend** ist und die Last die Auflager erreicht
6. Wiederholen bis Ziel-Massenanteil erreicht

---

## 👥 Entwickelt von

MCI – Semester 3, Softwaredesign  
Studienjahr 2025/2026

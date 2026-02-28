# graphRAG

Ein schlanker Einstieg für dieses Repository mit Fokus auf einer schnellen lokalen Installation.

## Voraussetzungen

- **Git** (zum Klonen des Repositories)
- **Python 3.10+**
- **pip** (Python-Paketmanager)
- Optional: **venv** (für eine isolierte Umgebung)

## Installation Guide

### 1) Repository klonen

```bash
git clone <REPO_URL>
cd graphRAG
```

### 2) Virtuelle Umgebung erstellen und aktivieren (empfohlen)

```bash
python -m venv .venv
source .venv/bin/activate
```

> Unter Windows (PowerShell):
>
> ```powershell
> python -m venv .venv
> .\.venv\Scripts\Activate.ps1
> ```

### 3) Abhängigkeiten installieren

Falls eine `requirements.txt` vorhanden ist:

```bash
pip install -r requirements.txt
```

Falls stattdessen ein `pyproject.toml` verwendet wird:

```bash
pip install -e .
```

### 4) Konfiguration

Wenn das Projekt Umgebungsvariablen benötigt, eine `.env` Datei anlegen:

```bash
cp .env.example .env
```

Danach die Werte in `.env` anpassen (z. B. API Keys, Modellnamen, Datenbank-URL).

### 5) Anwendung starten

Je nach Projektstruktur z. B.:

```bash
python main.py
```

oder

```bash
python -m src.main
```

## Verifikation

Nach dem Start sollten keine Import- oder Konfigurationsfehler erscheinen.

Optionaler schneller Check:

```bash
python --version
pip --version
```

## Troubleshooting

- **`ModuleNotFoundError`**: Prüfen, ob die virtuelle Umgebung aktiv ist und Dependencies installiert wurden.
- **`Permission denied`**: Bei Unix-Systemen Dateirechte prüfen (`chmod +x ...`).
- **Falsche Python-Version**: Mit `python --version` prüfen und ggf. eine passende Version verwenden.

---

Wenn du magst, kann ich als nächsten Schritt eine projektspezifische README-Version erstellen (mit den tatsächlichen Start-, Test- und Build-Befehlen dieses Repos).

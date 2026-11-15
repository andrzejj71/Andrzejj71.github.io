#!/usr/bin/env python3
"""Aktualizuje wszystkie dane naraz i zapisuje je w jednym pliku nba_data.json.

Uruchamia po kolei build_players.py, build_teams.py i build_teams_detail.py
(muszą leżeć w tym samym folderze), a potem skleja wyniki w nba_data.json.
Uruchom:  python aktualizuj_wszystko.py
"""
import json
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent


def run(script):
    print(f"\n=== {script} ===")
    return subprocess.run([sys.executable, script], cwd=here).returncode == 0


def load(name):
    return json.loads((here / name).read_text(encoding="utf-8"))


if not run("build_players.py") or not run("build_teams.py"):
    sys.exit("Błąd przy pobieraniu graczy lub drużyn. Plik nba_data.json nie został zapisany.")

data = {"players": load("players.json"), "teams": load("teams.json")}
if run("build_teams_detail.py"):
    data["detail"] = load("teams_detail.json")
else:
    print("Uwaga: nie udało się pobrać szczegółów drużyn (H2H, składy). Reszta danych zostanie zapisana.")

(here / "nba_data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"\nGotowe: nba_data.json (graczy: {len(data['players'])}, drużyn: {len(data['teams'])}).")
print("Teraz kliknij na stronie przycisk 'Wczytaj wszystko' i wybierz ten plik.")

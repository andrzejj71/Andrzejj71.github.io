#!/usr/bin/env python3
"""Generuje teams.json: bilans i winrate wszystkich drużyn NBA w sezonie 2026-27.

Dane pochodzą z nba.com (biblioteka nba_api).
Uruchom:  pip install nba_api  &&  python build_teams.py
"""
import json
import time

from nba_api.stats.endpoints import leaguestandingsv3
from nba_api.stats.static import teams as static_teams

SEASON = "2026-27"


def fetch():
    for _ in range(3):
        try:
            return leaguestandingsv3.LeagueStandingsV3(season=SEASON, timeout=60).get_data_frames()[0]
        except Exception:
            time.sleep(3)
    raise SystemExit("Nie udało się pobrać danych z nba.com. Spróbuj ponownie za chwilę.")


abbreviations = {t["id"]: t["abbreviation"] for t in static_teams.get_teams()}
result = []
for row in fetch().to_dict("records"):
    wins, losses = int(row["WINS"]), int(row["LOSSES"])
    games = wins + losses
    result.append({
        "team": abbreviations.get(int(row["TeamID"]), ""),
        "name": f'{row.get("TeamCity", "")} {row.get("TeamName", "")}'.strip(),
        "w": wins,
        "l": losses,
        "pct": round(wins / games * 100, 1) if games else 0,
        "home": row.get("HOME", ""),
        "road": row.get("ROAD", ""),
        "l10": row.get("L10", ""),
        "streak": row.get("strCurrentStreak", ""),
    })

result.sort(key=lambda t: -t["pct"])
with open("teams.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
print(f"Zapisano teams.json: {len(result)} drużyn")
for t in result[:5]:
    print(t["team"], f'{t["w"]}-{t["l"]}', f'{t["pct"]}%')

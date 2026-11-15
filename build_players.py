#!/usr/bin/env python3
"""Generuje players.json dla karty gracza: wszyscy gracze NBA z sezonu 2026-27,
którzy mają w sezonie co najmniej MIN_EACH punktów, zbiórek, asyst i trafionych trójek.

Dane pochodzą z nba.com (biblioteka nba_api).
Uruchom:  pip install nba_api  &&  python build_players.py
"""
import json
import time

from nba_api.stats.endpoints import leaguegamelog, leaguestandingsv3, playerindex

SEASON = "2026-27"
LAST_N = 10      # ile ostatnich meczów na wykresie
MIN_EACH = 1     # minimalna suma sezonowa KAŻDEJ statystyki: PTS, REB, AST, 3PM
KEYS = {"pts": "PTS", "reb": "REB", "ast": "AST", "tpm": "FG3M"}


def fetch(endpoint, **kwargs):
    for _ in range(3):
        try:
            return endpoint(timeout=60, **kwargs).get_data_frames()[0]
        except Exception:
            time.sleep(3)
    raise SystemExit("Nie udało się pobrać danych z nba.com. Spróbuj ponownie za chwilę.")


log = fetch(leaguegamelog.LeagueGameLog, season=SEASON, player_or_team_abbreviation="P")
standings = fetch(leaguestandingsv3.LeagueStandingsV3, season=SEASON)
index = fetch(playerindex.PlayerIndex, season=SEASON)

records = {int(r.TeamID): [int(r.WINS), int(r.LOSSES)] for r in standings.itertuples()}
positions = {int(r.PERSON_ID): r.POSITION for r in index.itertuples()}


def default_line(values):
    return int(sum(values) / len(values)) + 0.5


players = []
for pid, games in log.groupby("PLAYER_ID"):
    games = games.sort_values("GAME_DATE")
    if any(games[col].sum() < MIN_EACH for col in KEYS.values()):
        continue

    last = games.tail(LAST_N)
    latest = last.iloc[-1]
    stats = {}
    for key, col in KEYS.items():
        values = [int(x) for x in last[col]]
        stats[key] = [default_line(values), max(max(values) + 2, 6), values]

    name = latest.PLAYER_NAME
    record = records.get(int(latest.TEAM_ID))
    players.append({
        "id": int(pid),
        "n": name,
        "ini": "".join(w[0] for w in name.split()[:2]).upper(),
        "team": latest.TEAM_ABBREVIATION,
        "pos": positions.get(int(pid), "") or "NBA",
        "opp": None,
        "time": "",
        "home": False,
        "real": "nba.com",
        "rec": record,
        "recNote": "Brak bilansu drużyny w danych.",
        "o": [("@" if "@" in m else "") + m.split()[-1] for m in last.MATCHUP],
        "s": stats,
    })

players.sort(key=lambda p: p["n"])
with open("players.json", "w", encoding="utf-8") as f:
    json.dump(players, f, ensure_ascii=False, separators=(",", ":"))
print(f"Zapisano players.json: {len(players)} graczy")

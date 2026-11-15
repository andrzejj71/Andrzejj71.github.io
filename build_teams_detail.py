#!/usr/bin/env python3
"""Generuje teams_detail.json: dla każdej drużyny NBA ostatnie wyniki, H2H oraz statystyki
składu (starty, średnie minuty, odsetek meczów z grą we wszystkich 4 kwartach).

Dane pochodzą z nba.com (nba_api). Skrypt robi jedno zapytanie na każdy rozegrany mecz,
więc trwa kilka minut.
Uruchom:  pip install nba_api  &&  python build_teams_detail.py
"""
import json
import time
import warnings
import urllib.request
from collections import defaultdict

import pandas as pd
from nba_api.stats.endpoints import gamerotation, leaguegamelog
from nba_api.stats.static import teams as static_teams

warnings.filterwarnings("ignore", category=DeprecationWarning)

SEASONS = ["2026-27", "2025-26", "2024-25"]   # pierwszy = bieżący sezon; reszta tylko do H2H
LAST_RESULTS = 10   # ile ostatnich wyników na wykresach
LAST_LINEUP = 12    # z ilu ostatnich meczów liczymy starty i minuty
TENTHS = 10         # GameRotation podaje czas w dziesiątych częściach sekundy
QUARTER = 7200      # 12 minut w dziesiątych częściach sekundy


SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"


def next_games():
    """Najbliższy mecz każdej drużyny: terminarz nba.com, a gdy się nie uda, tablice wyników na kolejne dni."""
    out = {}

    def add(home, away, ts="", label=""):
        out.setdefault(home, {"opp": away, "home": True, "ts": ts, "label": label})
        out.setdefault(away, {"opp": home, "home": False, "ts": ts, "label": label})

    try:
        import requests
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com"}
        data = requests.get(SCHEDULE_URL, headers=headers, timeout=60).json()
        games = [g for d in data["leagueSchedule"]["gameDates"] for g in d["games"]
                 if g.get("gameStatus") == 1 and g["gameId"][:3] in ("002", "004")]
        for g in sorted(games, key=lambda g: g["gameDateTimeUTC"]):
            add(g["homeTeam"]["teamTricode"], g["awayTeam"]["teamTricode"], g["gameDateTimeUTC"])
        if out:
            return out
    except Exception as e:
        print(f"Terminarz z cdn.nba.com niedostępny ({e}). Próbuję tablic wyników...")

    try:
        from datetime import date, timedelta
        from nba_api.stats.endpoints import scoreboardv2
        ids = {t["id"]: t["abbreviation"] for t in static_teams.get_teams()}
        for i in range(21):
            day = date.today() + timedelta(days=i)
            res = fetch(scoreboardv2.ScoreboardV2, game_date=day.strftime("%m/%d/%Y"))
            if res is None:
                continue
            for r in res.get_data_frames()[0].itertuples():
                if int(r.GAME_STATUS_ID) == 1 and str(r.GAME_ID)[:3] in ("002", "004"):
                    add(ids[int(r.HOME_TEAM_ID)], ids[int(r.VISITOR_TEAM_ID)], "", day.strftime("%d.%m"))
            if len(out) >= 30:
                break
            time.sleep(0.6)
    except Exception as e:
        print(f"Uwaga: nie udało się pobrać terminarza ({e}), rywale nie będą wybierani automatycznie.")
    return out


def fetch(fn, **kw):
    for _ in range(3):
        try:
            return fn(timeout=60, **kw)
        except Exception:
            time.sleep(3)
    return None


logs = []
for season in SEASONS:
    res = fetch(leaguegamelog.LeagueGameLog, season=season)
    if res is None:
        raise SystemExit("Nie udało się pobrać danych z nba.com. Spróbuj za chwilę.")
    logs.append(res.get_data_frames()[0])
cur, everything = logs[0], pd.concat(logs)

# H2H: ostatnie 3 spotkania każdej pary (we wszystkich pobranych sezonach)
h2h = defaultdict(list)
for gid, g in everything.groupby("GAME_ID"):
    if len(g) != 2:
        continue
    a, b = sorted(g.itertuples(), key=lambda r: r.TEAM_ABBREVIATION)
    h2h[f"{a.TEAM_ABBREVIATION}-{b.TEAM_ABBREVIATION}"].append(
        (a.GAME_DATE, a.TEAM_ABBREVIATION, int(a.PTS), b.TEAM_ABBREVIATION, int(b.PTS)))
h2h_out = {}
for key, games in h2h.items():
    games.sort(reverse=True)
    h2h_out[key] = [[f"{d[8:]}.{d[5:7]}.{d[:4]}", a, ap, b, bp] for d, a, ap, b, bp in games[:3]]

# Wyniki i bilans drużyn
game_total = cur.groupby("GAME_ID")["PTS"].sum()
teams, windows = {}, {}
for tid, g in cur.groupby("TEAM_ID"):
    g = g.sort_values("GAME_DATE")
    last = g.tail(LAST_RESULTS)
    abbr = g.iloc[-1].TEAM_ABBREVIATION
    teams[abbr] = {
        "id": int(tid),
        "n": g.iloc[-1].TEAM_NAME,
        "rec": [int((g.WL == "W").sum()), int((g.WL == "L").sum())],
        "p": [int(x) for x in last.PTS],
        "o": [int(game_total[r.GAME_ID] - r.PTS) for r in last.itertuples()],
        "pl": [],
    }
    windows[int(tid)] = (abbr, list(g.tail(LAST_LINEUP).GAME_ID))

# Skład: starty, minuty i kwartały z rotacji w każdym meczu
needed = sorted({gid for _, ids in windows.values() for gid in ids})
stats = defaultdict(list)   # (team_id, player_id) -> [(game_id, min, starter, full4, name)]
for i, gid in enumerate(needed, 1):
    res = fetch(gamerotation.GameRotation, game_id=gid)
    if res is None:
        continue
    for df in res.get_data_frames():
        for (tid, pid), rows in df.groupby(["TEAM_ID", "PERSON_ID"]):
            tid, pid = int(tid), int(pid)
            if tid not in windows or gid not in windows[tid][1]:
                continue
            quarters, minutes, starter = set(), 0.0, False
            for r in rows.itertuples():
                start, end = float(r.IN_TIME_REAL), float(r.OUT_TIME_REAL)
                minutes += (end - start) / TENTHS / 60
                starter = starter or start == 0
                for q in range(4):
                    if start < (q + 1) * QUARTER and end > q * QUARTER:
                        quarters.add(q)
            name = f"{rows.iloc[0].PLAYER_FIRST} {rows.iloc[0].PLAYER_LAST}"
            stats[(tid, pid)].append((gid, minutes, starter, len(quarters) == 4, name))
    print(f"\rMecze: {i}/{len(needed)}", end="", flush=True)
    time.sleep(0.6)
print()

for (tid, pid), rows in stats.items():
    n = len(rows)
    teams[windows[tid][0]]["pl"].append([
        rows[0][4],
        sum(1 for r in rows if r[2]),
        round(sum(r[1] for r in rows) / n, 1),
        round(100 * sum(1 for r in rows if r[3]) / n),
        n,
        1 if any(r[0] == windows[tid][1][-1] for r in rows) else 0,   # czy zagrał w ostatnim meczu drużyny
        pid,                                                           # numer gracza (do zdjęcia)
    ])
for t in teams.values():
    t["pl"].sort(key=lambda p: (-p[1], -p[2]))
    t["pl"] = t["pl"][:8]

upcoming = next_games()
print(f"Terminarz: najbliższe mecze dla {len(upcoming)} drużyn.")
for abbr, nxt in upcoming.items():
    if abbr in teams:
        teams[abbr]["next"] = nxt

with open("teams_detail.json", "w", encoding="utf-8") as f:
    json.dump({"teams": teams, "h2h": h2h_out}, f, ensure_ascii=False, separators=(",", ":"))
total_min = [sum(p[2] for p in t["pl"]) for t in teams.values() if t["pl"]]
print(f"Zapisano teams_detail.json: {len(teams)} drużyn")
print(f"Kontrola: suma średnich minut najczęściej grających ok. {sum(total_min) / len(total_min):.0f} (powinno być blisko 200-240)")

#!/usr/bin/env python3
"""Relevé quotidien du positionnement du site via l'API Google Search Console.

Usage :
  python gsc_tracker.py             enregistre les données de J-3
"""

import argparse
import csv
from collections import defaultdict
from datetime import date, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

from seo_tracker.config import (
    CATCH_UP_DAYS,
    DELAY_DAYS,
    DISCOVER_DAYS,
    DISCOVER_LIMIT,
    DISCOVER_MAX_POSITION,
    DISCOVER_MIN_IMPRESSIONS,
    DISCOVER_MIN_POSITION,
    KEY_FILE,
    KEYWORDS_FILE,
    OUTPUT_FILE,
    REPORT_FILE,
    SITE,
)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
COLUMNS = ["date", "keyword", "page", "position", "clicks", "impressions", "ctr"]


def get_service():
    creds = service_account.Credentials.from_service_account_file(
        KEY_FILE, scopes=SCOPES
    )
    return build("searchconsole", "v1", credentials=creds)


def load_keywords():
    keywords = []
    for line in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            keywords.append(line)
    return keywords


def fetch_rows(service, day):
    body = {
        "startDate": day,
        "endDate": day,
        "dimensions": ["query", "page"],
        "rowLimit": 25000,
    }
    response = service.searchanalytics().query(siteUrl=SITE, body=body).execute()
    return response.get("rows", [])


def read_existing():
    if not OUTPUT_FILE.exists():
        return []
    with OUTPUT_FILE.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def recorded_days():
    """Retourne les dates déjà enregistrées avec leur total d'impressions."""
    totals = defaultdict(int)
    for row in read_existing():
        totals[row["date"]] += int(row["impressions"] or 0)
    return totals


def build_records(day, keywords, rows):
    by_keyword = {k: [] for k in keywords}
    for row in rows:
        query, page = row["keys"]
        if query.lower() in by_keyword:
            by_keyword[query.lower()].append((page, row))

    records = []
    for keyword in keywords:
        matches = by_keyword[keyword]
        if not matches:
            # Aucune impression ce jour-là : on garde une ligne pour la continuité
            records.append([day, keyword, "", "", 0, 0, ""])
            continue
        # Plusieurs pages possibles : une ligne par page, la mieux classée d'abord
        # (position la plus basse, puis le plus d'impressions en cas d'égalité)
        matches.sort(key=lambda m: (m[1]["position"], -m[1]["impressions"]))
        for page, row in matches:
            records.append([
                day,
                keyword,
                page,
                round(row["position"], 2),
                int(row["clicks"]),
                int(row["impressions"]),
                round(row["ctr"], 4),
            ])
    return records


def write_records(day, records):
    """Écrit les lignes du jour en remplaçant celles déjà présentes pour cette date."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    kept = [row for row in read_existing() if row["date"] != day]
    new = [dict(zip(COLUMNS, record)) for record in records]
    # Tri stable : l'ordre est chronologique même si on met à jour une date ancienne
    all_rows = sorted(kept + new, key=lambda row: row["date"])

    # Écriture dans un fichier temporaire puis remplacement, pour ne jamais
    # laisser un CSV à moitié écrit en cas d'erreur
    tmp_file = OUTPUT_FILE.with_suffix(".csv.tmp")
    with tmp_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)
    tmp_file.replace(OUTPUT_FILE)


def discover(service, days):
    """Affiche les requêtes proches de la page 1 qui ne sont pas encore suivies."""
    end = date.today() - timedelta(days=DELAY_DAYS)
    start = end - timedelta(days=days - 1)
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": ["query"],
        "rowLimit": 25000,
    }
    response = service.searchanalytics().query(siteUrl=SITE, body=body).execute()
    rows = response.get("rows", [])

    tracked = set(load_keywords())
    candidates = [
        row
        for row in rows
        if row["keys"][0].lower() not in tracked
        and DISCOVER_MIN_POSITION <= row["position"] <= DISCOVER_MAX_POSITION
        and row["impressions"] >= DISCOVER_MIN_IMPRESSIONS
    ]
    candidates.sort(key=lambda row: row["impressions"], reverse=True)

    print(f"Période : du {start} au {end} ({days} jours)")
    print(
        f"{len(rows)} requêtes remontées par Google, {len(candidates)} candidates "
        f"(position {DISCOVER_MIN_POSITION} à {DISCOVER_MAX_POSITION}, "
        f"au moins {DISCOVER_MIN_IMPRESSIONS} impressions, hors mots clés déjà suivis)"
    )
    if not candidates:
        return

    print()
    print(f"{'Position':>8}  {'Impr.':>6}  {'Clics':>5}  Requête")
    for row in candidates[:DISCOVER_LIMIT]:
        print(
            f"{row['position']:8.1f}  {row['impressions']:6.0f}  "
            f"{row['clicks']:5.0f}  {row['keys'][0]}"
        )
    if len(candidates) > DISCOVER_LIMIT:
        print(f"... et {len(candidates) - DISCOVER_LIMIT} autres (limite d'affichage : {DISCOVER_LIMIT})")


def summarize_run(end, fetched, empty):
    """Phrase de résumé d'un rattrapage, reprise telle quelle par la notification."""
    if not fetched:
        return f"rien à relever, {end} déjà enregistré"
    caught_up = [day for day in fetched if day != end]
    parts = []
    if end in fetched:
        parts.append(f"{end} relevé")
    if caught_up:
        label = "jour rattrapé" if len(caught_up) == 1 else "jours rattrapés"
        parts.append(f"{len(caught_up)} {label} ({', '.join(caught_up)})")
    summary = ", ".join(parts)
    if empty:
        summary += f". Aucune donnée chez Google pour : {', '.join(empty)}"
    return summary


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--test", action="store_true", help="vérifie l'accès à la propriété Google Search Console")
    parser.add_argument("--date", help="enregistre une date précise (au format AAA-MM-DD)")
    parser.add_argument("--update", action="store_true", help="remplace les données si la date est déjà enregistrée")
    parser.add_argument("--catch-up", dest="catch_up", nargs="?", type=int, const=CATCH_UP_DAYS, metavar="N", help=f"relève aussi les N jours précédents s'ils manquent (défaut : {CATCH_UP_DAYS})",)
    parser.add_argument("--discover", action="store_true", help="affiche les mots clés candidats non suivis")
    parser.add_argument("--days", type=int, default=DISCOVER_DAYS, help=f"période analysée par --discover en jours (défaut : {DISCOVER_DAYS})")
    parser.add_argument("--report", action="store_true", help="génère le rapport HTML à partir du CSV (open data/report.html)")
    args = parser.parse_args()
    if args.catch_up is not None and args.catch_up < 0:
        parser.error("--catch-up attend un nombre de jours positif")

    if args.report:
        # Import ici : le reste du script fonctionne même sans plotly installé
        from seo_tracker.report import generate_report

        generate_report(OUTPUT_FILE, REPORT_FILE)
        return

    service = get_service()

    if args.discover:
        discover(service, args.days)
        return

    if args.test:
        entries = service.sites().list().execute().get("siteEntry", [])
        if not entries:
            print(
                "Aucune propriété accessible : vérifier que le compte de service "
                "a bien été ajouté dans Search Console."
            )
        for entry in entries:
            print(f"{entry['siteUrl']} ({entry['permissionLevel']})")
        return

    end = (
        date.fromisoformat(args.date)
        if args.date
        else date.today() - timedelta(days=DELAY_DAYS)
    )
    if args.catch_up is None:
        days = [end]
    else:
        days = [end - timedelta(days=n) for n in range(args.catch_up, -1, -1)]

    keywords = load_keywords()
    recorded = recorded_days()
    fetched = []
    empty = []

    for day in days:
        key = day.isoformat()
        already_logged = key in recorded
        if already_logged and not args.update:
            if args.catch_up is None:
                print(f"{key} déjà enregistré. Relancer avec --update pour remplacer les données.")
                return
            if recorded[key] > 0:
                print(f"{key} déjà enregistré.")
                continue
            # Jour enregistré sans aucune impression : Google n'avait sans doute pas
            # encore publié ses données, on le relève à nouveau
            print(f"{key} enregistré sans impression, nouvelle tentative.")

        rows = fetch_rows(service, key)
        records = build_records(key, keywords, rows)
        write_records(key, records)
        fetched.append(key)
        if not rows:
            empty.append(key)

        action = "mises à jour" if already_logged else "ajoutées"
        print(f"{key} : {len(records)} lignes {action} ({len(rows)} lignes remontées par Google).")

    if args.catch_up is not None:
        print(f"Résumé : {summarize_run(end.isoformat(), fetched, empty)}")


if __name__ == "__main__":
    main()

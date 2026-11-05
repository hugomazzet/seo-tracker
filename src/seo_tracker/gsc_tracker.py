#!/usr/bin/env python3
"""Relevé quotidien du positionnement du site via l'API Google Search Console.

Usage :
  python gsc_tracker.py --test                          vérifie l'accès à la propriété
  python gsc_tracker.py                                 enregistre les données de J-3
  python gsc_tracker.py --update                        remplace les données de J-3
  python gsc_tracker.py --date 2026-11-05               enregistre une date précise
  python gsc_tracker.py --date 2026-11-05 --update      remplace les données d'une date déjà enregistrée
"""

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parents[2]
SITE = "sc-domain:hugomazet.com"
KEY_FILE = BASE_DIR / "secrets" / "service-account.json"
KEYWORDS_FILE = BASE_DIR / "inputs" / "keywords.txt"
OUTPUT_FILE = BASE_DIR / "data" / "positions.csv"

# Search Console publie ses données avec 2 à 3 jours de retard
DELAY_DAYS = 3
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


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--date")
    parser.add_argument(
        "--update",
        action="store_true",
        help="remplace les données si la date est déjà enregistrée",
    )
    args = parser.parse_args()

    service = get_service()

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

    day = args.date or (date.today() - timedelta(days=DELAY_DAYS)).isoformat()
    already_logged = any(row["date"] == day for row in read_existing())
    if already_logged and not args.update:
        print(f"{day} déjà enregistré. Relancer avec --update pour remplacer les données.")
        return

    keywords = load_keywords()
    rows = fetch_rows(service, day)
    records = build_records(day, keywords, rows)
    write_records(day, records)

    action = "mises à jour" if already_logged else "ajoutées"
    print(f"{day} : {len(records)} lignes {action} ({len(rows)} lignes remontées par Google).")


if __name__ == "__main__":
    main()

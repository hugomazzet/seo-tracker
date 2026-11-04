#!/usr/bin/env python3
"""Relevé quotidien du positionnement du site via l'API Google Search Console.

Usage :
  python gsc_tracker.py --test          vérifie l'accès à la propriété
  python gsc_tracker.py                 enregistre les données de J-3
  python gsc_tracker.py --date 2026-11-05
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


def day_already_logged(day):
    if not OUTPUT_FILE.exists():
        return False
    with OUTPUT_FILE.open(encoding="utf-8", newline="") as f:
        return any(row["date"] == day for row in csv.DictReader(f))


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


def append_records(records):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    is_new = not OUTPUT_FILE.exists()
    with OUTPUT_FILE.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(COLUMNS)
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--date")
    args = parser.parse_args()

    service = get_service()

    if args.test:
        entries = service.sites().list().execute().get("siteEntry", [])
        if not entries:
            print(
                "Aucune propriété accessible : vérifie que le compte de service "
                "a bien été ajouté dans Search Console."
            )
        for entry in entries:
            print(f"{entry['siteUrl']} ({entry['permissionLevel']})")
        return

    day = args.date or (date.today() - timedelta(days=DELAY_DAYS)).isoformat()
    if day_already_logged(day):
        print(f"{day} déjà enregistré, rien à faire.")
        return

    keywords = load_keywords()
    rows = fetch_rows(service, day)
    records = build_records(day, keywords, rows)
    append_records(records)
    print(f"{day} : {len(records)} lignes ajoutées ({len(rows)} lignes remontées par Google).")


if __name__ == "__main__":
    main()

"""Outils partagés par les tests : fichiers temporaires et faux service Google.

Aucun test n'appelle l'API Search Console ni ne touche aux fichiers du projet
(inputs/, data/) : tous les chemins sont redirigés vers un dossier temporaire.
"""

import sys
from types import SimpleNamespace

import pytest

import seo_tracker.gsc_tracker as tracker


def gsc_row(query, page, position, impressions, clicks=0):
    """Ligne telle que renvoyée par l'API Search Console (dimensions query, page)."""
    return {
        "keys": [query, page],
        "position": position,
        "clicks": clicks,
        "impressions": impressions,
        "ctr": clicks / impressions if impressions else 0,
    }


class FakeService:
    """Imite service.searchanalytics().query(siteUrl=..., body=...).execute().

    rows : liste de lignes renvoyée pour toute requête, ou dictionnaire
    {date: lignes} pour répondre selon la date demandée (startDate). La
    pagination (rowLimit, startRow) est respectée comme par la vraie API.
    """

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def searchanalytics(self):
        return self

    def query(self, siteUrl, body):
        self.calls.append({"siteUrl": siteUrl, **body})
        if isinstance(self.rows, dict):
            rows = self.rows.get(body["startDate"], [])
        else:
            rows = self.rows
        start = body.get("startRow", 0)
        page = rows[start:start + body["rowLimit"]]
        return SimpleNamespace(execute=lambda: {"rows": page} if page else {})

    def days_fetched(self):
        return [call["startDate"] for call in self.calls]


@pytest.fixture
def files(tmp_path, monkeypatch):
    """Redirige les fichiers du relevé vers un dossier temporaire."""
    paths = SimpleNamespace(
        keywords=tmp_path / "inputs" / "keywords.txt",
        output=tmp_path / "data" / "positions.csv",
        log=tmp_path / "data" / "fetch_log.csv",
        report=tmp_path / "data" / "report.html",
    )
    paths.keywords.parent.mkdir()
    monkeypatch.setattr(tracker, "KEYWORDS_FILE", paths.keywords)
    monkeypatch.setattr(tracker, "OUTPUT_FILE", paths.output)
    monkeypatch.setattr(tracker, "FETCH_LOG_FILE", paths.log)
    monkeypatch.setattr(tracker, "REPORT_FILE", paths.report)
    return paths


@pytest.fixture
def run(monkeypatch):
    """Lance la commande seo-tracker avec un faux service.

    Usage : run(service, "--date", "2026-11-20", "--catch-up", "2")
    """

    def _run(service, *args):
        monkeypatch.setattr(tracker, "get_service", lambda: service)
        monkeypatch.setattr(sys, "argv", ["seo-tracker", *args])
        tracker.main()

    return _run

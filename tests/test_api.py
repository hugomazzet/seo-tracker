"""Pagination des appels à l'API Search Console."""

import pytest

import seo_tracker.gsc_tracker as tracker
from conftest import FakeService, gsc_row


def _rows(count):
    return [gsc_row(f"requête {i}", "https://x/", 10.0, 1) for i in range(count)]


@pytest.fixture(autouse=True)
def small_pages(monkeypatch):
    # Pages de 3 lignes pour tester la pagination sans générer 25 000 lignes
    monkeypatch.setattr(tracker, "ROW_LIMIT", 3)


@pytest.mark.parametrize(
    ("total", "start_rows"),
    [
        (7, [0, 3, 6]),  # plusieurs pages, la dernière incomplète
        (6, [0, 3, 6]),  # dernière page pile pleine : une requête de plus, vide
        (2, [0]),  # une seule page
        (0, [0]),  # aucune donnée
    ],
)
def test_query_all_recupere_toutes_les_pages(total, start_rows):
    service = FakeService(_rows(total))
    rows = tracker.query_all(service, {"startDate": "2026-11-20", "endDate": "2026-11-20"})
    assert len(rows) == total
    assert [call["startRow"] for call in service.calls] == start_rows
    assert all(call["rowLimit"] == 3 for call in service.calls)


def test_fetch_rows_interroge_la_propriete_sur_un_jour():
    service = FakeService(_rows(1))
    tracker.fetch_rows(service, "2026-11-20")
    call = service.calls[0]
    assert call["siteUrl"] == tracker.SITE
    assert (call["startDate"], call["endDate"]) == ("2026-11-20", "2026-11-20")
    assert call["dimensions"] == ["query", "page"]

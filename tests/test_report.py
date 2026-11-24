"""Calculs et génération du rapport HTML."""

from datetime import date, timedelta

import pytest

from seo_tracker.report import (
    LOW_IMPRESSIONS,
    TREND_DAYS,
    best_per_day,
    generate_report,
    group_by_keyword,
    rank_pages,
    summarize,
    table_html,
    top_impressions_html,
    weighted_position,
)

LAST_DAY = date(2026, 11, 21)


def row(day, keyword, page, position, impressions, clicks=0):
    """Ligne telle que la renvoie load_rows. day : date ou nombre de jours avant LAST_DAY."""
    if isinstance(day, int):
        day = LAST_DAY - timedelta(days=day)
    return {
        "date": day.isoformat(),
        "keyword": keyword,
        "page": page,
        "position": position,
        "clicks": clicks,
        "impressions": impressions,
    }


# --- weighted_position et best_per_day ----------------------------------------


def test_weighted_position_pondere_par_les_impressions():
    items = [row(0, "k", "p", 10.0, 30), row(1, "k", "p", 20.0, 10)]
    assert weighted_position(items) == (12.5, 40)


def test_weighted_position_sans_impression_fait_une_moyenne_simple():
    items = [row(0, "k", "p", 10.0, 0), row(1, "k", "p", 20.0, 0)]
    assert weighted_position(items) == (15.0, 0)


def test_weighted_position_vide():
    assert weighted_position([]) == (None, 0)


def test_best_per_day_garde_la_page_la_mieux_classee():
    rows = [row(0, "k", "/b", 15.0, 200), row(0, "k", "/a", 3.0, 1), row(0, "k", "", None, 0)]
    assert [r["page"] for r in best_per_day(rows)] == ["/a"]


# --- Tableaux du haut ---------------------------------------------------------


def test_rank_pages_classe_par_position_et_ecarte_les_pages_peu_vues():
    rows = [
        row(0, "kw1", "https://x/a", 5.0, 10),
        row(1, "kw2", "https://x/a", 15.0, 30),
        row(0, "kw1", "https://x/b", 3.0, LOW_IMPRESSIONS - 1),
        row(0, "kw1", "https://x/c", 8.0, 20),
        row(0, "kw3", "", None, 0),
    ]
    pages = rank_pages(rows)
    assert [p["page"] for p in pages] == ["https://x/c", "https://x/a"]
    assert pages[1] == {"page": "https://x/a", "position": 12.5, "impressions": 40, "keywords": 2}


def test_top_impressions_classe_par_impressions_sur_tout_l_historique():
    rows = [
        row(30, "ancien", "/a", 10.0, 500),  # hors des 7 jours, mais compté
        row(0, "recent", "/a", 10.0, 50),
        row(0, "jamais vu", "", None, 0),
    ]
    html = top_impressions_html(summarize(group_by_keyword(rows), LAST_DAY))
    assert html.index("ancien") < html.index("recent")
    assert "jamais vu" not in html


# --- Situation actuelle -------------------------------------------------------


def test_summarize_compare_les_deux_periodes():
    rows = []
    for n in range(2 * TREND_DAYS):
        recent = n < TREND_DAYS
        rows.append(row(n, "k", "/a", 10.0 if recent else 20.0, 10, clicks=1 if recent else 0))
    (item,) = summarize(group_by_keyword(rows), LAST_DAY)
    assert item["average"] == 10.0
    assert item["change"] == 10.0  # 10 places gagnées
    assert item["change_reliable"]
    assert item["recent_impressions"] == 10 * TREND_DAYS
    assert item["recent_clicks"] == TREND_DAYS
    # Totaux sur tout l'historique
    assert item["impressions"] == 20 * TREND_DAYS
    assert item["overall"] == 15.0


def test_summarize_evolution_peu_fiable_sous_le_seuil():
    rows = [row(0, "k", "/a", 10.0, LOW_IMPRESSIONS), row(TREND_DAYS, "k", "/a", 20.0, 1)]
    (item,) = summarize(group_by_keyword(rows), LAST_DAY)
    assert item["change"] == 10.0
    assert not item["change_reliable"]


def test_situation_actuelle_masque_les_mots_cles_inactifs():
    rows = [
        row(0, "actif", "/a", 10.0, 5),
        row(TREND_DAYS, "inactif", "/a", 10.0, 50),  # vu juste avant la fenêtre
    ]
    html = table_html(summarize(group_by_keyword(rows), LAST_DAY))
    assert "actif" in html
    assert "inactif" not in html


def test_situation_actuelle_vide():
    rows = [row(TREND_DAYS, "inactif", "/a", 10.0, 50)]
    html = table_html(summarize(group_by_keyword(rows), LAST_DAY))
    assert "<table>" not in html
    assert f"Aucune impression sur les {TREND_DAYS} derniers jours" in html


# --- Génération complète ------------------------------------------------------


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "positions.csv"
    path.write_text(
        "date,keyword,page,position,clicks,impressions,ctr\n"
        "2026-11-20,mot un,https://x/a,8.0,1,20,0.05\n"
        "2026-11-20,mot deux,,,0,0,\n"
        "2026-11-21,mot un,https://x/a,6.0,0,25,0.0\n"
        "2026-11-21,mot deux,https://x/b,30.0,0,3,0.0\n",
        encoding="utf-8",
    )
    return path


def test_generate_report_ecrit_un_fichier_autonome(tmp_path, csv_file):
    output = tmp_path / "out" / "report.html"
    assert generate_report(csv_file, output)
    html = output.read_text(encoding="utf-8")
    for title in [
        "Pages les mieux positionnées",
        "Mots clés les plus vus",
        f"Situation actuelle sur {TREND_DAYS} jours",
        "Position par mot clé",
        "Impressions et clics",
    ]:
        assert title in html
    assert "Données du 20/11/2026 au 21/11/2026 (2 jours relevés, 2 mots clés suivis)" in html


def test_generate_report_sans_csv(tmp_path, capsys):
    assert not generate_report(tmp_path / "absent.csv", tmp_path / "report.html")
    assert "n'existe pas encore" in capsys.readouterr().out
    assert not (tmp_path / "report.html").exists()

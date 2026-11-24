"""Relevé quotidien, --update et rattrapage (--catch-up) avec le journal des relevés."""

import csv

from conftest import FakeService, gsc_row
from seo_tracker.gsc_tracker import is_published, log_fetch, read_fetch_log

PUBLISHED_NO_MATCH = [gsc_row("requête non suivie", "https://x/", 30.0, 4)]
PUBLISHED_MATCH = [gsc_row("mon mot", "https://x/", 8.0, 12, clicks=1)]


def _csv_days(path):
    with path.open(encoding="utf-8", newline="") as f:
        return sorted({row["date"] for row in csv.DictReader(f)})


# --- is_published -----------------------------------------------------------


def test_is_published_se_fie_au_journal():
    assert is_published("2026-11-20", {"2026-11-20": 0}, {"2026-11-20": 5})
    assert not is_published("2026-11-20", {"2026-11-20": 0}, {"2026-11-20": 0})


def test_is_published_sans_journal_applique_l_ancienne_regle():
    assert is_published("2026-11-20", {"2026-11-20": 3}, {})
    assert not is_published("2026-11-20", {"2026-11-20": 0}, {})


def test_log_fetch_trie_et_remplace(files):
    log_fetch("2026-11-21", 4)
    log_fetch("2026-11-19", 0)
    log_fetch("2026-11-19", 7)
    assert read_fetch_log() == {"2026-11-19": 7, "2026-11-21": 4}
    assert files.log.read_text(encoding="utf-8").splitlines() == [
        "date,google_rows",
        "2026-11-19,7",
        "2026-11-21,4",
    ]


# --- Relevé simple et --update ----------------------------------------------


def test_releve_une_date(files, run, capsys):
    files.keywords.write_text("mon mot\n", encoding="utf-8")
    service = FakeService({"2026-11-20": PUBLISHED_MATCH})
    run(service, "--date", "2026-11-20")
    assert _csv_days(files.output) == ["2026-11-20"]
    assert read_fetch_log() == {"2026-11-20": 1}
    assert "2026-11-20 : 1 lignes ajoutées (1 lignes remontées par Google)." in capsys.readouterr().out


def test_date_deja_enregistree_n_est_pas_relevee(files, run, capsys):
    files.keywords.write_text("mon mot\n", encoding="utf-8")
    service = FakeService({"2026-11-20": PUBLISHED_MATCH})
    run(service, "--date", "2026-11-20")
    run(service, "--date", "2026-11-20")
    assert service.days_fetched() == ["2026-11-20"]
    assert "déjà enregistré. Relancer avec --update" in capsys.readouterr().out


def test_update_releve_a_nouveau(files, run):
    files.keywords.write_text("mon mot\n", encoding="utf-8")
    service = FakeService({"2026-11-20": PUBLISHED_MATCH})
    run(service, "--date", "2026-11-20")
    run(service, "--date", "2026-11-20", "--update")
    assert service.days_fetched() == ["2026-11-20", "2026-11-20"]


# --- Rattrapage ---------------------------------------------------------------


def test_scenario_de_rattrapage(files, run, capsys):
    """18 : non publié, 19 : publié sans impression sur le mot clé, 20 : publié."""
    files.keywords.write_text("mon mot\n", encoding="utf-8")
    data = {"2026-11-18": [], "2026-11-19": PUBLISHED_NO_MATCH, "2026-11-20": PUBLISHED_MATCH}
    args = ("--date", "2026-11-20", "--catch-up", "2")

    service = FakeService(data)
    run(service, *args)
    assert service.days_fetched() == ["2026-11-18", "2026-11-19", "2026-11-20"]
    assert read_fetch_log() == {"2026-11-18": 0, "2026-11-19": 1, "2026-11-20": 1}
    out = capsys.readouterr().out
    assert (
        "Résumé : 2026-11-20 relevé, 2 jours rattrapés (2026-11-18, 2026-11-19). "
        "Aucune donnée chez Google pour : 2026-11-18"
    ) in out

    # 2e lancement : seul le 18 (non publié) est relevé à nouveau ; le 19, publié
    # mais sans impression sur le mot clé suivi, est complet
    service = FakeService(data)
    run(service, *args)
    assert service.days_fetched() == ["2026-11-18"]
    assert "2026-11-18 enregistré sans données Google, nouvelle tentative." in capsys.readouterr().out

    # Google publie le 18 : il est relevé une dernière fois, puis plus rien
    data["2026-11-18"] = PUBLISHED_MATCH
    service = FakeService(data)
    run(service, *args)
    assert service.days_fetched() == ["2026-11-18"]
    service = FakeService(data)
    run(service, *args)
    assert service.days_fetched() == []
    assert "Résumé : rien à relever, 2026-11-20 déjà enregistré" in capsys.readouterr().out


def test_rattrapage_d_un_csv_sans_journal(files, run):
    """Jours relevés avant l'ajout du journal : ancienne règle, puis journal."""
    files.keywords.write_text("mon mot\n", encoding="utf-8")
    files.output.parent.mkdir(parents=True)
    files.output.write_text(
        "date,keyword,page,position,clicks,impressions,ctr\n"
        "2026-11-19,mon mot,,,0,0,\n"
        "2026-11-20,mon mot,https://x/,8.0,1,12,0.0833\n",
        encoding="utf-8",
    )
    data = {"2026-11-19": PUBLISHED_NO_MATCH, "2026-11-20": PUBLISHED_MATCH}

    service = FakeService(data)
    run(service, "--date", "2026-11-20", "--catch-up", "1")
    # Le 19 (0 impression, pas de journal) est relevé une fois, le 20 est complet
    assert service.days_fetched() == ["2026-11-19"]
    assert read_fetch_log() == {"2026-11-19": 1}

    service = FakeService(data)
    run(service, "--date", "2026-11-20", "--catch-up", "1")
    assert service.days_fetched() == []


def test_rattrapage_avec_update_releve_toute_la_fenetre(files, run):
    files.keywords.write_text("mon mot\n", encoding="utf-8")
    data = {"2026-11-19": PUBLISHED_MATCH, "2026-11-20": PUBLISHED_MATCH}
    run(FakeService(data), "--date", "2026-11-20", "--catch-up", "1")
    service = FakeService(data)
    run(service, "--date", "2026-11-20", "--catch-up", "1", "--update")
    assert service.days_fetched() == ["2026-11-19", "2026-11-20"]

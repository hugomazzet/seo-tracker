"""Options de la ligne de commande et phrase de résumé de la notification."""

import argparse
from datetime import date

import pytest

import seo_tracker.report
from seo_tracker.gsc_tracker import parse_date, summarize_run


# --- parse_date -------------------------------------------------------------


def test_parse_date_valide():
    assert parse_date("2026-11-05") == date(2026, 11, 5)


@pytest.mark.parametrize("value", ["2026-13-05", "2026-02-30", "05/11/2026", "2026-11", "hier", ""])
def test_parse_date_invalide(value):
    with pytest.raises(argparse.ArgumentTypeError, match="Format attendu : YYYY-MM-DD"):
        parse_date(value)


def test_date_invalide_affiche_un_message_clair(files, run, capsys):
    with pytest.raises(SystemExit) as exit_info:
        run(None, "--date", "2026-13-05")
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "date invalide : '2026-13-05'" in err
    assert "Traceback" not in err


def test_catch_up_negatif_refuse(files, run, capsys):
    with pytest.raises(SystemExit):
        run(None, "--catch-up", "-1")
    assert "--catch-up attend un nombre de jours positif" in capsys.readouterr().err


# --- --report ---------------------------------------------------------------


@pytest.fixture
def report_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(seo_tracker.report, "generate_report", lambda *paths: calls.append(paths))
    return calls


def test_report_seul_sans_message(files, run, report_calls, capsys):
    run(None, "--report")
    assert report_calls == [(files.output, files.report)]
    assert "ignore" not in capsys.readouterr().out


def test_report_signale_les_options_ignorees(files, run, report_calls, capsys):
    # Le service vaut None : un relevé provoquerait une erreur, donc aucun n'est fait
    run(None, "--report", "--catch-up", "3", "--date", "2026-11-05")
    assert len(report_calls) == 1
    assert "--report ignore les autres options (--date, --catch-up)" in capsys.readouterr().out


# --- summarize_run ----------------------------------------------------------


@pytest.mark.parametrize(
    ("fetched", "empty", "expected"),
    [
        ([], [], "rien à relever, 2026-11-20 déjà enregistré"),
        (["2026-11-20"], [], "2026-11-20 relevé"),
        (["2026-11-19", "2026-11-20"], [], "2026-11-20 relevé, 1 jour rattrapé (2026-11-19)"),
        (["2026-11-18", "2026-11-19"], [], "2 jours rattrapés (2026-11-18, 2026-11-19)"),
        (
            ["2026-11-20"],
            ["2026-11-20"],
            "2026-11-20 relevé. Aucune donnée chez Google pour : 2026-11-20",
        ),
    ],
)
def test_summarize_run(fetched, empty, expected):
    assert summarize_run("2026-11-20", fetched, empty) == expected

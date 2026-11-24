"""Construction et écriture des lignes du CSV."""

import csv

from conftest import gsc_row
from seo_tracker.gsc_tracker import COLUMNS, build_records, write_records

DAY = "2026-11-20"


def test_ligne_vide_quand_le_mot_cle_n_a_pas_d_impression():
    records = build_records(DAY, ["mot absent"], [gsc_row("autre requête", "https://x/a", 4.0, 10)])
    assert records == [[DAY, "mot absent", "", "", 0, 0, ""]]


def test_une_ligne_par_page_la_mieux_classee_d_abord():
    rows = [
        gsc_row("mot", "https://x/b", 12.0, 30),
        gsc_row("mot", "https://x/a", 4.0, 5),
        gsc_row("mot", "https://x/c", 4.0, 50),
    ]
    records = build_records(DAY, ["mot"], rows)
    # Position la plus basse d'abord, puis le plus d'impressions en cas d'égalité
    assert [r[2] for r in records] == ["https://x/c", "https://x/a", "https://x/b"]


def test_correspondance_exacte_et_insensible_a_la_casse():
    rows = [
        gsc_row("photographe paris pas cher", "https://x/a", 3.0, 10),
        gsc_row("Photographe Paris", "https://x/b", 7.0, 20),
    ]
    records = build_records(DAY, ["photographe paris"], rows)
    assert len(records) == 1
    assert records[0][2] == "https://x/b"


def test_valeurs_arrondies():
    row = gsc_row("mot", "https://x/a", 8.123456, 3, clicks=1)
    assert build_records(DAY, ["mot"], [row]) == [[DAY, "mot", "https://x/a", 8.12, 1, 3, 0.3333]]


def _read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_write_records_remplace_le_jour_et_garde_les_autres(files):
    write_records("2026-11-19", [["2026-11-19", "mot", "https://x/a", 5.0, 0, 3, 0.0]])
    write_records("2026-11-21", [["2026-11-21", "mot", "https://x/a", 6.0, 0, 4, 0.0]])
    write_records("2026-11-20", [["2026-11-20", "mot", "https://x/a", 7.0, 0, 5, 0.0]])
    # Mise à jour d'un jour déjà présent : ses lignes sont remplacées
    write_records("2026-11-20", [["2026-11-20", "mot", "https://x/b", 9.0, 1, 8, 0.125]])

    rows = _read(files.output)
    assert list(rows[0]) == COLUMNS
    assert [(r["date"], r["page"]) for r in rows] == [
        ("2026-11-19", "https://x/a"),
        ("2026-11-20", "https://x/b"),
        ("2026-11-21", "https://x/a"),
    ]
    assert not files.output.with_suffix(".csv.tmp").exists()

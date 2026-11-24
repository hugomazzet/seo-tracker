"""Lecture de la liste des mots clés (inputs/keywords.txt)."""

from seo_tracker.gsc_tracker import load_keywords


def test_ignore_commentaires_et_lignes_vides(files):
    files.keywords.write_text("# commentaire\n\nmot un\n   \n# autre\nmot deux\n", encoding="utf-8")
    assert load_keywords() == ["mot un", "mot deux"]


def test_normalise_casse_et_espaces(files):
    files.keywords.write_text("  Photographe Mariage  \n", encoding="utf-8")
    assert load_keywords() == ["photographe mariage"]


def test_ignore_les_doublons_et_les_signale(files, capsys):
    files.keywords.write_text("mot un\nautre\n  MOT UN \nautre\n", encoding="utf-8")
    assert load_keywords() == ["mot un", "autre"]
    out = capsys.readouterr().out
    assert "Mot clé en double ignoré dans keywords.txt : mot un" in out
    assert "Mot clé en double ignoré dans keywords.txt : autre" in out


def test_garde_l_ordre_du_fichier(files):
    files.keywords.write_text("zèbre\nabeille\nmouton\n", encoding="utf-8")
    assert load_keywords() == ["zèbre", "abeille", "mouton"]

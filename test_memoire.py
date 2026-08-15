#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_memoire.py — Tests de la mémoire (index SQLite, recherche, doublons).

Lancer :  python -m unittest test_memoire
"""

import tempfile
import unittest
from pathlib import Path

import trier_documents as noyau
import memoire


def _op(base, nom, contenu, emetteur="EDF", categorie="Prive/Energie-Telecom",
        date="2026-03-12"):
    """Fabrique un fichier de test dans _a_trier + l'opération correspondante."""
    a_trier = base / noyau.DOSSIER_A_TRIER
    a_trier.mkdir(parents=True, exist_ok=True)
    source = a_trier / nom
    source.write_text(contenu)
    dossier_cible = base / "Prive" / date[:4] / "Energie-Telecom"
    return {
        "source_path": source, "source_name": nom, "classe": True,
        "emetteur": emetteur, "categorie": categorie, "confiance": 3,
        "date": date, "date_source": "document",
        "dossier_cible": dossier_cible,
        "nouveau_nom": f"{date}_{emetteur}_facture.pdf", "ocr": False,
    }


class TestHash(unittest.TestCase):
    def test_meme_contenu_meme_hash(self):
        with tempfile.TemporaryDirectory() as d:
            a = Path(d) / "a.pdf"; a.write_text("bonjour")
            b = Path(d) / "b.pdf"; b.write_text("bonjour")
            c = Path(d) / "c.pdf"; c.write_text("autre")
            self.assertEqual(memoire.hash_fichier(a), memoire.hash_fichier(b))
            self.assertNotEqual(memoire.hash_fichier(a), memoire.hash_fichier(c))


class TestEnregistrerEtChercher(unittest.TestCase):
    def test_enregistre_puis_trouve(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            op = _op(base, "facture.pdf", "contenu EDF")
            dest = op["dossier_cible"] / op["nouveau_nom"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("contenu EDF")   # simulate the moved file
            memoire.enregistrer(base, op, dest)

            # Recherche par émetteur et par année.
            self.assertEqual(len(memoire.chercher(base, "EDF")), 1)
            self.assertEqual(len(memoire.chercher(base, "EDF 2026")), 1)
            self.assertEqual(len(memoire.chercher(base, "URSSAF")), 0)

    def test_recherche_multi_mots(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for i, (em, dt) in enumerate([("EDF", "2025-01-01"), ("EDF", "2026-01-01"),
                                          ("CPAM", "2026-02-02")]):
                op = _op(base, f"f{i}.pdf", f"c{i}", emetteur=em, date=dt)
                dest = base / f"stock{i}.pdf"; dest.write_text(f"c{i}")
                memoire.enregistrer(base, op, dest)
            # « EDF 2026 » ne doit ramener que la facture EDF de 2026.
            r = memoire.chercher(base, "EDF 2026")
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0]["emetteur"], "EDF")
            self.assertEqual(r[0]["date_doc"], "2026-01-01")


class TestDoublons(unittest.TestCase):
    def test_doublon_dans_le_lot(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            op1 = _op(base, "a.pdf", "MEME CONTENU")
            op2 = _op(base, "b.pdf", "MEME CONTENU")   # contenu identique
            memoire.annoter_doublons(base, [op1, op2])
            # Le premier passe, le second est marqué doublon.
            self.assertFalse(op1["doublon"])
            self.assertTrue(op2["doublon"])
            self.assertEqual(op2["categorie"], noyau.DOSSIER_DOUBLONS)

    def test_doublon_contre_archive(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            # On classe un premier document (il entre dans la mémoire).
            op = _op(base, "orig.pdf", "CONTENU UNIQUE")
            chemin_journal = base / noyau.FICHIER_JOURNAL
            noyau.appliquer_operation(op, chemin_journal, lot="lot1")

            # On présente le MÊME contenu à trier : il doit être détecté doublon.
            op2 = _op(base, "copie.pdf", "CONTENU UNIQUE")
            memoire.annoter_doublons(base, [op2])
            self.assertTrue(op2["doublon"])


class TestRetraitAAnnulation(unittest.TestCase):
    def test_annuler_retire_de_la_memoire(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            op = _op(base, "x.pdf", "abc")
            chemin_journal = base / noyau.FICHIER_JOURNAL
            noyau.appliquer_operation(op, chemin_journal, lot="lot1")
            self.assertEqual(len(memoire.chercher(base, "EDF")), 1)

            # Annulation -> la fiche doit disparaître de la mémoire.
            noyau.annuler_operations(base, journaliser=lambda m: None)
            self.assertEqual(len(memoire.chercher(base, "EDF")), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

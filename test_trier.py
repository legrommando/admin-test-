#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_trier.py — Tests automatisés du moteur de tri (trier_documents.py).

But : vérifier automatiquement que les fonctions importantes se comportent
comme prévu, pour repérer tout de suite une régression si on modifie le code.

On teste UNIQUEMENT le moteur (pas la fenêtre), donc aucun écran n'est requis.
On n'a pas besoin de vrais PDF : pour les déplacements, de simples fichiers
« .pdf » vides suffisent (le moteur ne lit pas leur contenu pour déplacer).

Lancer les tests :
    python -m unittest test_trier
ou simplement :
    python test_trier.py
"""

import tempfile
import unittest
from pathlib import Path

import trier_documents as noyau


# Un petit jeu de règles minimal, suffisant pour les tests (indépendant de
# regles.yaml, pour que les tests restent stables même si tu modifies le YAML).
REGLES_TEST = {
    "reglages": {"seuil_confiance_min": 2},
    "emetteurs": [
        {
            "emetteur": "EDF", "domaine": "Prive", "destination": "Energie-Telecom",
            "type": "facture-electricite",
            "mots_cles": ["EDF", "electricite de france", "facture d'electricite"],
        },
        {
            "emetteur": "URSSAF", "domaine": "Pro", "destination": "Social-URSSAF",
            "type": "cotisations-sociales",
            "mots_cles": ["URSSAF", "cotisations sociales", "travailleur independant"],
        },
    ],
}


class TestExtraireDate(unittest.TestCase):
    """Vérifie la reconnaissance des différents formats de date."""

    def test_format_iso(self):
        self.assertEqual(noyau.extraire_date("Relevé du 2026-05-20 payé"), "2026-05-20")

    def test_format_numerique_4_chiffres(self):
        self.assertEqual(noyau.extraire_date("Facture 12/03/2026"), "2026-03-12")

    def test_format_numerique_2_chiffres(self):
        self.assertEqual(noyau.extraire_date("le 12/03/26"), "2026-03-12")

    def test_mois_en_lettres(self):
        self.assertEqual(noyau.extraire_date("émis le 5 avril 2026"), "2026-04-05")

    def test_mois_abrege_avec_point(self):
        self.assertEqual(noyau.extraire_date("le 9 janv. 2026"), "2026-01-09")

    def test_date_invalide_ignoree(self):
        # 32/13 n'existe pas : aucune date ne doit être retournée.
        self.assertIsNone(noyau.extraire_date("valeur 32/13/2026 bizarre"))

    def test_aucune_date(self):
        self.assertIsNone(noyau.extraire_date("aucun chiffre de date ici"))


class TestIdentifierEmetteur(unittest.TestCase):
    """Vérifie l'identification de l'émetteur par mots-clés."""

    def test_reconnaissance_edf(self):
        texte = "EDF Electricite de France — votre facture d'electricite"
        emetteur, score = noyau.identifier_emetteur(texte, REGLES_TEST)
        self.assertIsNotNone(emetteur)
        self.assertEqual(emetteur["emetteur"], "EDF")
        self.assertGreaterEqual(score, 2)

    def test_insensible_accents_casse(self):
        # « électricité » (avec accents/majuscules) doit matcher « electricite ».
        texte = "ÉLECTRICITÉ DE FRANCE - Facture d'Électricité"
        emetteur, score = noyau.identifier_emetteur(texte, REGLES_TEST)
        self.assertEqual(emetteur["emetteur"], "EDF")

    def test_document_inconnu(self):
        emetteur, score = noyau.identifier_emetteur("texte sans rapport", REGLES_TEST)
        self.assertEqual(score, 0)


class TestComposerDestination(unittest.TestCase):
    """Vérifie la construction du nom de fichier et du dossier cible."""

    def test_nom_et_dossier(self):
        em = REGLES_TEST["emetteurs"][0]  # EDF
        categorie, dossier, nom = noyau.composer_destination(
            Path("/tmp/base"), em, "2026-03-12")
        self.assertEqual(categorie, "Prive/Energie-Telecom")
        self.assertEqual(nom, "2026-03-12_EDF_facture-electricite.pdf")
        self.assertEqual(dossier, Path("/tmp/base/Prive/2026/Energie-Telecom"))


class TestCollision(unittest.TestCase):
    """Vérifie que l'on ne réutilise jamais un nom déjà pris."""

    def test_suffixe_incremental(self):
        with tempfile.TemporaryDirectory() as d:
            dossier = Path(d)
            (dossier / "a.pdf").write_text("x")
            # Le nom est pris -> on doit obtenir a_2.pdf
            resultat = noyau.chemin_sans_collision(dossier / "a.pdf")
            self.assertEqual(resultat.name, "a_2.pdf")


class TestClasserEtAnnuler(unittest.TestCase):
    """Vérifie le déplacement réel, le journal, et l'annulation par lot."""

    def _fabriquer_operation(self, base, nom):
        """Crée un faux PDF dans _a_trier et l'opération EDF correspondante."""
        a_trier = base / noyau.DOSSIER_A_TRIER
        a_trier.mkdir(parents=True, exist_ok=True)
        source = a_trier / nom
        source.write_text("faux pdf")   # contenu sans importance pour un déplacement
        em = REGLES_TEST["emetteurs"][0]
        categorie, dossier_cible, nouveau_nom = noyau.composer_destination(
            base, em, "2026-03-12")
        return {
            "source_path": source, "source_name": nom, "classe": True,
            "emetteur": "EDF", "categorie": categorie, "confiance": 3,
            "date": "2026-03-12", "date_source": "document",
            "dossier_cible": dossier_cible, "nouveau_nom": nouveau_nom, "ocr": False,
        }

    def test_appliquer_puis_annuler_tout(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            journal = base / noyau.FICHIER_JOURNAL
            op = self._fabriquer_operation(base, "facture.pdf")
            dest = noyau.appliquer_operation(op, journal, lot="lotA")

            self.assertTrue(dest.exists())                 # le fichier a bougé
            self.assertFalse(op["source_path"].exists())   # plus à l'origine
            self.assertTrue(journal.exists())              # journal écrit

            nb, ignores = noyau.annuler_operations(base)
            self.assertEqual(nb, 1)
            self.assertTrue((base / noyau.DOSSIER_A_TRIER / "facture.pdf").exists())
            self.assertFalse(journal.exists())             # journal vidé -> supprimé

    def test_annuler_dernier_lot_seulement(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            journal = base / noyau.FICHIER_JOURNAL
            # Lot 1 : un fichier
            op1 = self._fabriquer_operation(base, "doc1.pdf")
            noyau.appliquer_operation(op1, journal, lot="lot1")
            # Lot 2 : un autre fichier
            op2 = self._fabriquer_operation(base, "doc2.pdf")
            noyau.appliquer_operation(op2, journal, lot="lot2")

            # On n'annule QUE le dernier lot -> doc2 revient, doc1 reste classé.
            nb, ignores = noyau.annuler_operations(base, dernier_lot_seulement=True)
            self.assertEqual(nb, 1)
            self.assertTrue((base / noyau.DOSSIER_A_TRIER / "doc2.pdf").exists())
            # doc1 est toujours rangé, et le journal existe encore (lot1 dedans).
            restants = list((base / "Prive").rglob("*.pdf"))
            self.assertEqual(len(restants), 1)
            self.assertTrue(journal.exists())


class TestUrgence(unittest.TestCase):
    """Vérifie la détection d'échéance et le calcul d'urgence."""

    def test_extraire_echeance(self):
        self.assertEqual(
            noyau.extraire_echeance("Facture. À payer avant le 20/08/2026. Merci"),
            "2026-08-20")
        self.assertEqual(
            noyau.extraire_echeance("Date limite de paiement : 2026-09-01"),
            "2026-09-01")
        self.assertIsNone(noyau.extraire_echeance("Aucune échéance mentionnée ici."))

    def test_niveaux(self):
        import datetime
        auj = datetime.date(2026, 8, 15)
        self.assertEqual(noyau.niveau_urgence("2026-08-01", False, auj)[0], 4)  # retard
        self.assertEqual(noyau.niveau_urgence("2026-08-20", False, auj)[0], 3)  # <=7j
        self.assertEqual(noyau.niveau_urgence("2026-09-10", False, auj)[0], 2)  # <=30j
        self.assertEqual(noyau.niveau_urgence("2026-12-01", False, auj)[0], 1)  # lointaine
        self.assertEqual(noyau.niveau_urgence(None, True, auj)[0], 3)   # action sans date
        self.assertEqual(noyau.niveau_urgence(None, False, auj)[0], 0)  # rien

    def test_ordonner_par_urgence(self):
        ops = [
            {"source_name": "a", "urgence": 1, "echeance": "2026-12-01"},
            {"source_name": "b", "urgence": 4, "echeance": "2026-08-01"},
            {"source_name": "c", "urgence": 3, "echeance": "2026-08-20"},
        ]
        ordre = [o["source_name"] for o in noyau.ordonner_par_urgence(ops)]
        self.assertEqual(ordre, ["b", "c", "a"])  # du plus urgent au moins urgent

    def test_copie_dans_priorites(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            a_trier = base / noyau.DOSSIER_A_TRIER
            a_trier.mkdir(parents=True)
            source = a_trier / "facture.pdf"
            source.write_text("contenu")
            em = REGLES_TEST["emetteurs"][0]
            categorie, dossier_cible, nouveau_nom = noyau.composer_destination(
                base, em, "2026-03-12")
            op = {
                "source_path": source, "source_name": "facture.pdf", "classe": True,
                "emetteur": "EDF", "categorie": categorie, "confiance": 3,
                "date": "2026-03-12", "date_source": "document",
                "dossier_cible": dossier_cible, "nouveau_nom": nouveau_nom,
                "ocr": False, "echeance": "2026-08-18", "urgence": 3,
                "urgence_label": "urgent",
            }
            noyau.appliquer_operation(op, base / noyau.FICHIER_JOURNAL, lot="lot1")
            # Une copie doit exister dans _priorites, préfixée par l'échéance.
            copies = list((base / noyau.DOSSIER_PRIORITES).glob("*.pdf"))
            self.assertEqual(len(copies), 1)
            self.assertTrue(copies[0].name.startswith("2026-08-18__"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

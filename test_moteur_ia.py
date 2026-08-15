#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_moteur_ia.py — Tests du moteur IA locale, SANS vrai modèle.

On lance un faux serveur Ollama sur localhost qui imite les réponses du vrai
Ollama. Cela permet de vérifier tout le circuit (détection, envoi des images,
lecture du JSON, construction de l'opération) sans télécharger de modèle.

Lancer :  python -m unittest test_moteur_ia
"""

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import moteur_ia

# Règles minimales pour les tests (indépendantes de regles.yaml).
REGLES_TEST = {
    "reglages": {
        "dossiers_prive": ["Energie-Telecom", "Sante"],
        "dossiers_pro": ["Social-URSSAF"],
    },
    "emetteurs": [
        {"emetteur": "EDF", "domaine": "Prive", "destination": "Energie-Telecom",
         "type": "facture", "mots_cles": ["EDF"]},
    ],
}

# Réponse que notre faux modèle renverra pour /api/chat.
REPONSE_MODELE = {
    "domaine": "Prive", "destination": "Energie-Telecom", "emetteur": "EDF",
    "type": "facture-electricite", "date": "2026-03-12", "montant": 84.5,
    "confiance": 0.95,
}


class FauxOllama(BaseHTTPRequestHandler):
    """Faux serveur qui imite les deux routes d'Ollama utilisées."""

    def log_message(self, *args):
        pass  # silence

    def do_GET(self):
        if self.path == "/api/tags":
            self._json({"models": [{"name": "llama3.2-vision:latest"}]})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/chat":
            longueur = int(self.headers.get("Content-Length", 0))
            corps = json.loads(self.rfile.read(longueur))
            # On vérifie que des images ont bien été envoyées.
            images = corps["messages"][0].get("images", [])
            contenu = json.dumps(REPONSE_MODELE) if images else "{}"
            self._json({"message": {"content": contenu}})
        else:
            self.send_error(404)

    def _json(self, obj):
        donnees = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)


def _faire_pdf(chemin):
    """Fabrique un petit PDF de test (une page)."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    c = canvas.Canvas(str(chemin), pagesize=A4)
    c.drawString(80, 780, "EDF - Facture d'electricite - 12/03/2026")
    c.save()


class TestExtraireJson(unittest.TestCase):
    def test_json_pur(self):
        self.assertEqual(moteur_ia._extraire_json('{"a": 1}'), {"a": 1})

    def test_json_entoure_de_texte(self):
        texte = 'Voici le résultat : {"a": 1, "b": 2} merci.'
        self.assertEqual(moteur_ia._extraire_json(texte), {"a": 1, "b": 2})

    def test_texte_sans_json(self):
        with self.assertRaises(ValueError):
            moteur_ia._extraire_json("aucun json ici")


class TestDateValide(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(moteur_ia._date_valide("2026-03-12"))

    def test_ko(self):
        self.assertFalse(moteur_ia._date_valide("12/03/2026"))
        self.assertFalse(moteur_ia._date_valide(None))


class TestAvecFauxServeur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = HTTPServer(("127.0.0.1", 0), FauxOllama)
        cls.port = cls.serveur.server_address[1]
        cls.url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()

    def test_disponibilite(self):
        ok, message = moteur_ia.ollama_disponible(self.url, "llama3.2-vision")
        self.assertTrue(ok, message)

    def test_modele_absent(self):
        ok, message = moteur_ia.ollama_disponible(self.url, "modele-inexistant")
        self.assertFalse(ok)
        self.assertIn("pull", message)

    def test_analyse_complete(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            a_trier = base / moteur_ia.noyau.DOSSIER_A_TRIER
            a_trier.mkdir(parents=True)
            pdf = a_trier / "facture.pdf"
            _faire_pdf(pdf)

            op = moteur_ia.analyser_fichier_ia(
                pdf, REGLES_TEST, base, base_url=self.url, modele="llama3.2-vision")

            self.assertTrue(op["classe"])
            self.assertEqual(op["emetteur"], "EDF")
            self.assertEqual(op["categorie"], "Prive/Energie-Telecom")
            self.assertEqual(op["date"], "2026-03-12")
            self.assertEqual(op["nouveau_nom"],
                             "2026-03-12_EDF_facture-electricite.pdf")
            self.assertEqual(op["moteur"], "ia")


class TestRepliSansServeur(unittest.TestCase):
    def test_ollama_absent(self):
        # Port très improbable -> Ollama injoignable.
        ok, message = moteur_ia.ollama_disponible("http://127.0.0.1:1", timeout=1)
        self.assertFalse(ok)

    def test_analyse_replie_en_non_classe(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            a_trier = base / moteur_ia.noyau.DOSSIER_A_TRIER
            a_trier.mkdir(parents=True)
            pdf = a_trier / "x.pdf"
            _faire_pdf(pdf)
            op = moteur_ia.analyser_fichier_ia(
                pdf, REGLES_TEST, base, base_url="http://127.0.0.1:1")
            # IA injoignable -> non classé, mais pas de plantage.
            self.assertFalse(op["classe"])
            self.assertEqual(op["categorie"], moteur_ia.noyau.DOSSIER_NON_CLASSE)


if __name__ == "__main__":
    unittest.main(verbosity=2)

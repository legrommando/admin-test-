#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generer_pdf_test.py — Fabrique 3 PDF de test factices.

But : créer rapidement des documents d'exemple dans Administration/_a_trier
afin de vérifier que trier_documents.py les classe correctement.

Les 3 PDF générés :
  1) Une facture d'électricité EDF (privé, Energie-Telecom).
  2) Un appel de cotisations URSSAF (pro, Social-URSSAF).
  3) Un décompte de remboursement CPAM (privé, Sante).

Utilisation :
    python3 generer_pdf_test.py

Dépendance : reportlab (voir requirements.txt).
"""

from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ImportError:
    print("Erreur : le module 'reportlab' n'est pas installé.")
    print("Installe-le avec :  pip install -r requirements.txt")
    raise SystemExit(1)


# Dossier où déposer les PDF de test (le même que celui traité par le script).
DOSSIER_A_TRIER = Path("Administration") / "_a_trier"


def creer_pdf(nom_fichier, lignes):
    """Crée un PDF simple contenant les 'lignes' de texte fournies.

    Chaque élément de 'lignes' est écrit sur une nouvelle ligne du document.
    """
    chemin = DOSSIER_A_TRIER / nom_fichier
    c = canvas.Canvas(str(chemin), pagesize=A4)

    # Position de départ (coin haut-gauche, en points ; A4 fait 842 pt de haut).
    x = 60
    y = 780
    c.setFont("Helvetica", 12)

    for ligne in lignes:
        c.drawString(x, y, ligne)
        y -= 20  # on descend de 20 points à chaque ligne

    c.save()
    print(f"  Créé : {chemin}")


def main():
    # On s'assure que le dossier _a_trier existe.
    DOSSIER_A_TRIER.mkdir(parents=True, exist_ok=True)

    print("Génération des PDF de test...")

    # --- PDF 1 : Facture EDF (privé / Energie-Telecom) ---
    creer_pdf("facture_energie_vrac.pdf", [
        "EDF - Electricite de France",
        "Facture d'electricite",
        "Reference client : 4567891230",
        "Date de facture : 12/03/2026",
        "Montant total : 84,50 EUR",
        "Consommation du 01/02/2026 au 28/02/2026",
    ])

    # --- PDF 2 : URSSAF (pro / Social-URSSAF) ---
    creer_pdf("document_2.pdf", [
        "URSSAF",
        "Appel de cotisations sociales",
        "Travailleur independant",
        "Cotisations sociales dues au titre du 1er trimestre",
        "Date : 5 avril 2026",
        "Montant a payer : 1 250,00 EUR",
    ])

    # --- PDF 3 : CPAM (privé / Sante) ---
    creer_pdf("scan0003.pdf", [
        "Assurance Maladie - CPAM",
        "Releve de remboursements (decompte)",
        "Compte Ameli",
        "Date du releve : 2026-05-20",
        "Remboursement : 23,40 EUR",
    ])

    print("\nTermine. Lance maintenant :  python3 trier_documents.py")


if __name__ == "__main__":
    main()

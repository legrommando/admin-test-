#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trier_documents.py — Classement automatique de documents administratifs (PDF).

But du programme :
    Tu déposes des PDF « en vrac » dans le dossier Administration/_a_trier.
    Ce script les lit, devine l'émetteur et la catégorie, trouve la date,
    puis les renomme et les range dans une arborescence Privé / Pro.

Grands principes de SÉCURITÉ (voir aussi le README) :
    - Par défaut, on est en mode SIMULATION : on affiche ce qui SERAIT fait,
      on ne touche à AUCUN fichier. Il faut ajouter --execute pour agir.
    - On ne supprime jamais, on n'écrase jamais un fichier. En cas de
      collision de nom, on ajoute un suffixe _2, _3, ...
    - Chaque déplacement réel est enregistré dans journal.csv, ce qui permet
      d'annuler avec --annuler.

Utilisation rapide :
    python3 trier_documents.py                 # simulation (rien n'est touché)
    python3 trier_documents.py --execute       # range réellement les fichiers
    python3 trier_documents.py --annuler        # remet tout en place (via journal)

Ce script tient volontairement dans UN seul fichier, avec le minimum de
dépendances : pdfplumber (lecture des PDF) et PyYAML (lecture des règles).
"""

import argparse            # pour lire les options en ligne de commande
import csv                 # pour écrire et relire le journal des opérations
import datetime            # pour manipuler les dates
import os                  # pour lire la date de modification d'un fichier
import re                  # pour chercher les dates dans le texte (expressions régulières)
import shutil              # pour déplacer les fichiers (move)
import sys                 # pour arrêter proprement en cas d'erreur
import unicodedata         # pour retirer les accents lors des comparaisons
from pathlib import Path   # pour manipuler les chemins de façon simple et sûre

# Dépendances externes (voir requirements.txt).
# On les importe dans un try/except pour afficher un message clair si elles
# ne sont pas installées.
try:
    import yaml
except ImportError:
    print("Erreur : le module 'PyYAML' n'est pas installé.")
    print("Installe-le avec :  pip install -r requirements.txt")
    sys.exit(1)

try:
    import pdfplumber
except ImportError:
    print("Erreur : le module 'pdfplumber' n'est pas installé.")
    print("Installe-le avec :  pip install -r requirements.txt")
    sys.exit(1)


# =============================================================================
# Constantes : noms de dossiers et de fichiers
# =============================================================================
# On regroupe ici les noms « fixes » pour ne pas les répéter partout dans le
# code. Si tu veux renommer un dossier, tu changes la valeur ici.

DOSSIER_RACINE = "Administration"   # dossier principal qui contient tout
DOSSIER_A_TRIER = "_a_trier"        # là où tu déposes les PDF en vrac
DOSSIER_NON_CLASSE = "_non_classe"  # là où vont les documents non reconnus
FICHIER_REGLES = "regles.yaml"      # les règles de classement (éditable)
FICHIER_JOURNAL = "journal.csv"     # l'historique des déplacements

# Colonnes du journal.csv (dans cet ordre exact).
COLONNES_JOURNAL = [
    "date_operation",   # quand l'opération a eu lieu
    "nom_original",     # nom du fichier avant déplacement
    "chemin_original",  # chemin complet avant déplacement
    "nouveau_nom",      # nom du fichier après déplacement
    "nouveau_chemin",   # chemin complet après déplacement
    "categorie",        # catégorie retenue (ex : Prive/Energie-Telecom)
    "confiance",        # score de confiance du classement
]


# =============================================================================
# Petites fonctions utilitaires (texte)
# =============================================================================

def sans_accents(texte):
    """Retourne le texte en minuscules et SANS accents.

    Cela permet de comparer « Électricité » et « electricite » comme
    identiques. On s'en sert pour rendre la recherche de mots-clés plus
    tolérante.
    """
    # NFD décompose les caractères accentués (é -> e + accent),
    # puis on enlève les « accents » (catégorie Unicode Mn = Mark, nonspacing).
    texte_decompose = unicodedata.normalize("NFD", texte)
    texte_sans_accent = "".join(
        c for c in texte_decompose if unicodedata.category(c) != "Mn"
    )
    return texte_sans_accent.lower()


def nettoyer_pour_nom_fichier(texte):
    """Transforme un texte en un morceau de nom de fichier « propre ».

    On garde uniquement les lettres, chiffres et tirets. Les espaces
    deviennent des tirets. Utile pour construire des noms de fichiers
    sans caractères bizarres.
    """
    texte = texte.strip()
    # On remplace tout ce qui n'est pas lettre/chiffre par un tiret.
    texte = re.sub(r"[^0-9A-Za-zÀ-ÿ]+", "-", texte)
    # On enlève les tirets en trop au début / à la fin.
    return texte.strip("-")


# =============================================================================
# Lecture des règles (regles.yaml)
# =============================================================================

def charger_regles(chemin_regles):
    """Lit le fichier regles.yaml et retourne son contenu sous forme de dict.

    Si le fichier est absent ou mal formé, on arrête le programme avec un
    message clair.
    """
    chemin = Path(chemin_regles)
    if not chemin.exists():
        print(f"Erreur : le fichier de règles '{chemin}' est introuvable.")
        sys.exit(1)

    try:
        with open(chemin, "r", encoding="utf-8") as f:
            regles = yaml.safe_load(f)
    except yaml.YAMLError as erreur:
        print(f"Erreur : le fichier '{chemin}' contient une erreur YAML :")
        print(erreur)
        sys.exit(1)

    # Quelques vérifications de base pour éviter des plantages plus loin.
    if not regles or "emetteurs" not in regles:
        print(f"Erreur : le fichier '{chemin}' ne contient pas de section 'emetteurs'.")
        sys.exit(1)

    return regles


# =============================================================================
# Extraction du texte d'un PDF
# =============================================================================

def lire_texte_pdf(chemin_pdf):
    """Extrait tout le texte d'un PDF grâce à pdfplumber.

    Retourne une grande chaîne de caractères (le texte de toutes les pages
    collées ensemble). Si la lecture échoue, retourne une chaîne vide et
    affiche un avertissement.
    """
    morceaux_de_texte = []
    try:
        with pdfplumber.open(chemin_pdf) as pdf:
            for page in pdf.pages:
                # extract_text() peut retourner None si la page est vide.
                texte_page = page.extract_text() or ""
                morceaux_de_texte.append(texte_page)
    except Exception as erreur:
        # On ne veut pas que le programme s'arrête à cause d'un seul PDF
        # illisible : on prévient et on continue avec un texte vide.
        print(f"  ! Impossible de lire le PDF ({erreur}). Texte considéré vide.")
        return ""

    return "\n".join(morceaux_de_texte)


# =============================================================================
# Identification de l'émetteur et de la catégorie
# =============================================================================

def identifier_emetteur(texte, regles):
    """Devine l'émetteur du document à partir de son texte.

    Principe : pour chaque émetteur connu dans regles.yaml, on compte
    combien de ses mots-clés apparaissent dans le texte du document.
    L'émetteur ayant le meilleur score gagne.

    Retourne un couple (meilleur_emetteur, score) :
      - meilleur_emetteur : le dictionnaire de l'émetteur retenu, ou None
      - score             : le nombre de mots-clés trouvés (0 si aucun)
    """
    # On compare toujours sur du texte sans accents et en minuscules.
    texte_normalise = sans_accents(texte)

    meilleur_emetteur = None
    meilleur_score = 0

    for emetteur in regles["emetteurs"]:
        score = 0
        for mot_cle in emetteur.get("mots_cles", []):
            mot_cle_normalise = sans_accents(mot_cle)
            # On compte 1 point par mot-clé présent au moins une fois.
            if mot_cle_normalise in texte_normalise:
                score += 1

        # On garde l'émetteur qui a le plus de mots-clés trouvés.
        if score > meilleur_score:
            meilleur_score = score
            meilleur_emetteur = emetteur

    return meilleur_emetteur, meilleur_score


# =============================================================================
# Extraction de la date du document
# =============================================================================

# Table de correspondance des mois français -> numéro du mois.
MOIS_FR = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}


def extraire_date(texte):
    """Cherche une date dans le texte et la retourne au format AAAA-MM-JJ.

    On sait reconnaître trois formats courants en France :
      1) 12/03/2026   (ou 12-03-2026)
      2) 12 mars 2026
      3) 2026-03-12   (format ISO)

    Retourne une chaîne 'AAAA-MM-JJ' si une date valide est trouvée,
    sinon retourne None.
    """
    texte_normalise = sans_accents(texte)

    # --- Format 3 : 2026-03-12 (ISO, année en premier) ---
    # On le teste en premier car il est le moins ambigu.
    motif_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", texte_normalise)
    if motif_iso:
        annee, mois, jour = motif_iso.groups()
        date = _construire_date(annee, mois, jour)
        if date:
            return date

    # --- Format 1 : 12/03/2026 ou 12-03-2026 (jour/mois/année) ---
    motif_numerique = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", texte_normalise
    )
    if motif_numerique:
        jour, mois, annee = motif_numerique.groups()
        date = _construire_date(annee, mois, jour)
        if date:
            return date

    # --- Format 2 : 12 mars 2026 (jour mois-en-lettres année) ---
    motif_lettres = re.search(
        r"\b(\d{1,2})\s+([a-z]+)\s+(\d{4})\b", texte_normalise
    )
    if motif_lettres:
        jour, mois_texte, annee = motif_lettres.groups()
        numero_mois = MOIS_FR.get(mois_texte)
        if numero_mois:
            date = _construire_date(annee, numero_mois, jour)
            if date:
                return date

    # Aucune date reconnue.
    return None


def _construire_date(annee, mois, jour):
    """Construit une date 'AAAA-MM-JJ' à partir de morceaux, ou None si invalide.

    On vérifie que la date existe vraiment (par ex. le 32 janvier n'existe
    pas). Les paramètres peuvent être des chaînes ou des nombres.
    """
    try:
        d = datetime.date(int(annee), int(mois), int(jour))
        return d.strftime("%Y-%m-%d")
    except ValueError:
        # Date impossible (mauvais jour/mois) : on ignore.
        return None


def date_de_modification(chemin_fichier):
    """Retourne la date de dernière modification du fichier au format AAAA-MM-JJ.

    Sert de solution de secours quand aucune date n'est trouvée dans le
    texte du document.
    """
    horodatage = os.path.getmtime(chemin_fichier)
    d = datetime.date.fromtimestamp(horodatage)
    return d.strftime("%Y-%m-%d")


# =============================================================================
# Construction du chemin de destination et gestion des collisions
# =============================================================================

def chemin_sans_collision(chemin_voulu):
    """Retourne un chemin qui n'existe pas encore, pour ne rien écraser.

    Si 'dossier/2026-03-12_EDF_facture.pdf' existe déjà, on essaie
    '..._2.pdf', puis '..._3.pdf', etc., jusqu'à trouver un nom libre.
    """
    chemin = Path(chemin_voulu)
    if not chemin.exists():
        return chemin

    # On sépare le nom (sans extension) et l'extension (.pdf).
    dossier = chemin.parent
    tige = chemin.stem          # ex : 2026-03-12_EDF_facture
    extension = chemin.suffix   # ex : .pdf

    compteur = 2
    while True:
        nouveau_nom = f"{tige}_{compteur}{extension}"
        candidat = dossier / nouveau_nom
        if not candidat.exists():
            return candidat
        compteur += 1


# =============================================================================
# Journal des opérations (journal.csv)
# =============================================================================

def ajouter_au_journal(chemin_journal, ligne):
    """Ajoute une ligne au journal.csv (en le créant avec son en-tête si besoin)."""
    chemin = Path(chemin_journal)
    fichier_existe_deja = chemin.exists()

    # newline="" est recommandé par la doc Python pour écrire du CSV.
    with open(chemin, "a", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES_JOURNAL)
        # On écrit l'en-tête seulement la première fois.
        if not fichier_existe_deja:
            ecrivain.writeheader()
        ecrivain.writerow(ligne)


def lire_journal(chemin_journal):
    """Lit le journal.csv et retourne la liste de ses lignes (des dicts)."""
    chemin = Path(chemin_journal)
    if not chemin.exists():
        return []

    with open(chemin, "r", newline="", encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        return list(lecteur)


# =============================================================================
# Cœur du programme : traiter le dossier _a_trier
# =============================================================================

def traiter_dossier(base, regles, mode_execute):
    """Parcourt _a_trier et classe chaque PDF (ou simule le classement).

    Paramètres :
      - base         : chemin du dossier Administration
      - regles       : les règles chargées depuis regles.yaml
      - mode_execute : True = on déplace vraiment ; False = simulation
    """
    dossier_a_trier = base / DOSSIER_A_TRIER
    dossier_non_classe = base / DOSSIER_NON_CLASSE
    chemin_journal = base / FICHIER_JOURNAL

    # Seuil minimum de confiance, lu depuis les règles (2 par défaut).
    seuil = regles.get("reglages", {}).get("seuil_confiance_min", 2)

    if not dossier_a_trier.exists():
        print(f"Erreur : le dossier '{dossier_a_trier}' n'existe pas.")
        print("Crée-le et déposes-y tes PDF, puis relance le script.")
        sys.exit(1)

    # On récupère uniquement les fichiers .pdf (peu importe la casse), triés.
    fichiers_pdf = sorted(
        p for p in dossier_a_trier.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    )

    if not fichiers_pdf:
        print(f"Aucun PDF à traiter dans '{dossier_a_trier}'.")
        return

    # Petit rappel visible du mode en cours.
    if mode_execute:
        print(">>> MODE EXECUTION : les fichiers vont être RÉELLEMENT déplacés.\n")
    else:
        print(">>> MODE SIMULATION : rien ne sera modifié (ajoute --execute pour agir).\n")

    # Compteurs pour le résumé final.
    nb_classes = 0
    nb_non_classes = 0

    for chemin_pdf in fichiers_pdf:
        print(f"Fichier : {chemin_pdf.name}")

        # 1) Lire le texte du PDF.
        texte = lire_texte_pdf(chemin_pdf)

        # 2) Identifier l'émetteur / la catégorie.
        emetteur, score = identifier_emetteur(texte, regles)

        # 3) Décider : confiance suffisante ou non ?
        if emetteur is None or score < seuil:
            # --- Confiance trop faible : direction _non_classe ---
            nb_non_classes += 1
            categorie = "_non_classe"
            print(f"  -> Confiance faible (score {score} < seuil {seuil}).")

            # On ne renomme PAS : on garde le nom d'origine.
            destination = chemin_sans_collision(dossier_non_classe / chemin_pdf.name)

            if mode_execute:
                dossier_non_classe.mkdir(parents=True, exist_ok=True)
                shutil.move(str(chemin_pdf), str(destination))
                ajouter_au_journal(chemin_journal, {
                    "date_operation": datetime.datetime.now().isoformat(timespec="seconds"),
                    "nom_original": chemin_pdf.name,
                    "chemin_original": str(chemin_pdf),
                    "nouveau_nom": destination.name,
                    "nouveau_chemin": str(destination),
                    "categorie": categorie,
                    "confiance": score,
                })
                print(f"  -> Déplacé vers : {destination}")
            else:
                print(f"  -> SERAIT déplacé vers : {destination}")
            print()
            continue

        # --- Confiance suffisante : on classe pour de bon ---
        nb_classes += 1

        # 4) Trouver la date du document (ou repli sur la date de modif).
        date = extraire_date(texte)
        if date is None:
            date = date_de_modification(chemin_pdf)
            print(f"  ! Aucune date trouvée dans le texte : "
                  f"utilisation de la date de modification du fichier ({date}).")

        # L'année sert à créer le sous-dossier <annee>.
        annee = date[:4]

        # 5) Construire le nouveau nom : AAAA-MM-JJ_Emetteur_type.pdf
        nom_emetteur = nettoyer_pour_nom_fichier(emetteur["emetteur"])
        type_doc = nettoyer_pour_nom_fichier(emetteur.get("type", "document"))
        nouveau_nom = f"{date}_{nom_emetteur}_{type_doc}.pdf"

        # 6) Construire le dossier de destination : Domaine/annee/Destination
        domaine = emetteur["domaine"]           # "Prive" ou "Pro"
        sous_dossier = emetteur["destination"]  # ex : Energie-Telecom
        categorie = f"{domaine}/{sous_dossier}"
        dossier_cible = base / domaine / annee / sous_dossier

        # On évite d'écraser un fichier existant (suffixe _2, _3, ...).
        destination = chemin_sans_collision(dossier_cible / nouveau_nom)

        print(f"  -> Émetteur : {emetteur['emetteur']} "
              f"(catégorie {categorie}, confiance {score})")

        if mode_execute:
            dossier_cible.mkdir(parents=True, exist_ok=True)
            shutil.move(str(chemin_pdf), str(destination))
            ajouter_au_journal(chemin_journal, {
                "date_operation": datetime.datetime.now().isoformat(timespec="seconds"),
                "nom_original": chemin_pdf.name,
                "chemin_original": str(chemin_pdf),
                "nouveau_nom": destination.name,
                "nouveau_chemin": str(destination),
                "categorie": categorie,
                "confiance": score,
            })
            print(f"  -> Déplacé vers : {destination}")
        else:
            print(f"  -> SERAIT renommé/déplacé vers : {destination}")
        print()

    # Résumé final, toujours utile pour se rassurer.
    print("----- Résumé -----")
    print(f"  Classés        : {nb_classes}")
    print(f"  Non classés    : {nb_non_classes}")
    if not mode_execute:
        print("  (Simulation : aucun fichier n'a été modifié.)")


# =============================================================================
# Annulation : remettre les fichiers à leur place d'origine
# =============================================================================

def annuler(base):
    """Relit le journal.csv et remet chaque fichier à son emplacement d'origine.

    On procède dans l'ordre inverse (dernière opération annulée en premier),
    ce qui est plus sûr. On ne supprime rien : si le chemin d'origine est
    déjà occupé, on ajoute un suffixe pour ne rien écraser.
    """
    chemin_journal = base / FICHIER_JOURNAL
    lignes = lire_journal(chemin_journal)

    if not lignes:
        print("Rien à annuler : le journal est vide ou introuvable.")
        return

    print(f">>> Annulation de {len(lignes)} opération(s) à partir du journal.\n")

    nb_remis = 0
    lignes_restantes = []  # opérations que l'on n'a PAS pu annuler (à garder)

    # On parcourt à l'envers : on annule d'abord les opérations les plus récentes.
    for ligne in reversed(lignes):
        chemin_actuel = Path(ligne["nouveau_chemin"])
        chemin_origine_voulu = Path(ligne["chemin_original"])

        if not chemin_actuel.exists():
            # Le fichier n'est plus là où le journal l'attend : on prévient
            # et on conserve la ligne pour que tu puisses vérifier.
            print(f"  ! Introuvable, ignoré : {chemin_actuel}")
            lignes_restantes.append(ligne)
            continue

        # On ne veut jamais écraser : on cherche un nom libre à l'origine.
        destination = chemin_sans_collision(chemin_origine_voulu)

        # On recrée le dossier d'origine si besoin, puis on déplace.
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(chemin_actuel), str(destination))
        nb_remis += 1

        if destination == chemin_origine_voulu:
            print(f"  Remis : {chemin_actuel}  ->  {destination}")
        else:
            print(f"  Remis (nom ajusté) : {chemin_actuel}  ->  {destination}")

    # Si tout a été remis, on peut vider le journal ; sinon on garde les
    # lignes non traitées pour ne pas perdre d'information.
    if lignes_restantes:
        # On réécrit le journal avec seulement les lignes restantes.
        with open(chemin_journal, "w", newline="", encoding="utf-8") as f:
            ecrivain = csv.DictWriter(f, fieldnames=COLONNES_JOURNAL)
            ecrivain.writeheader()
            # On remet dans l'ordre chronologique d'origine.
            for ligne in reversed(lignes_restantes):
                ecrivain.writerow(ligne)
        print(f"\n{nb_remis} fichier(s) remis. "
              f"{len(lignes_restantes)} ligne(s) conservée(s) dans le journal.")
    else:
        # Tout a été annulé : on supprime le journal devenu inutile.
        chemin_journal.unlink(missing_ok=True)
        print(f"\n{nb_remis} fichier(s) remis. Journal vidé.")


# =============================================================================
# Point d'entrée : lecture des options et lancement
# =============================================================================

def main():
    """Lit les options de la ligne de commande et lance la bonne action."""
    analyseur = argparse.ArgumentParser(
        description="Classement automatique de documents administratifs (PDF).",
        epilog="Par défaut, le script est en mode SIMULATION (rien n'est modifié).",
    )
    analyseur.add_argument(
        "--base",
        default=DOSSIER_RACINE,
        help=f"Dossier principal à traiter (par défaut : {DOSSIER_RACINE}).",
    )
    analyseur.add_argument(
        "--regles",
        default=FICHIER_REGLES,
        help=f"Fichier de règles YAML (par défaut : {FICHIER_REGLES}).",
    )
    analyseur.add_argument(
        "--execute",
        action="store_true",
        help="Effectue réellement les déplacements (sinon : simulation).",
    )
    analyseur.add_argument(
        "--annuler",
        action="store_true",
        help="Annule les déplacements en relisant journal.csv.",
    )
    options = analyseur.parse_args()

    base = Path(options.base)

    # Cas 1 : on veut annuler. Pas besoin des règles pour cela.
    if options.annuler:
        annuler(base)
        return

    # Cas 2 : classement (simulation par défaut, réel avec --execute).
    regles = charger_regles(options.regles)
    traiter_dossier(base, regles, mode_execute=options.execute)


# Cette ligne classique fait que main() ne s'exécute que si on lance
# directement ce fichier (et pas si on l'importe ailleurs).
if __name__ == "__main__":
    main()

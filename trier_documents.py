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

# --- OCR (facultatif) : lire le texte des PDF qui sont des IMAGES (scans) ---
# Beaucoup de documents administratifs sont des scans : ce sont des images,
# sans texte « sélectionnable ». pdfplumber n'y voit alors aucun texte.
# L'OCR (reconnaissance optique de caractères) permet de « lire » ces images.
#
# On a besoin de deux choses :
#   - pypdfium2 : pour transformer une page PDF en image (il est déjà installé
#     avec pdfplumber, donc presque toujours présent) ;
#   - pytesseract + le logiciel Tesseract : le moteur d'OCR proprement dit.
#
# Tout est OPTIONNEL : si l'OCR n'est pas disponible, le programme fonctionne
# normalement, il se contente de ne pas lire les scans (qui iront alors dans
# _non_classe). On ne bloque jamais pour ça.
try:
    import pypdfium2
    import pytesseract
    # On vérifie que le logiciel Tesseract est bien installé sur la machine.
    pytesseract.get_tesseract_version()
    OCR_DISPONIBLE = True
except Exception:
    OCR_DISPONIBLE = False


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
    "lot",              # identifiant du « lot » de classement (pour annuler un seul lot)
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

# En dessous de ce nombre de caractères, on considère que pdfplumber n'a
# pratiquement rien lu (PDF probablement scanné) : on tentera alors l'OCR.
SEUIL_TEXTE_OCR = 20

# On n'OCRise que les premières pages (l'émetteur et la date sont presque
# toujours en début de document), pour rester rapide.
OCR_PAGES_MAX = 5


def lire_texte_pdf(chemin_pdf, autoriser_ocr=True):
    """Extrait le texte d'un PDF. Retourne un couple (texte, ocr_utilise).

    On essaie d'abord pdfplumber (texte « sélectionnable », rapide et fiable).
    Si le document est un SCAN (une image, donc quasiment aucun texte trouvé)
    et que l'OCR est disponible, on tente alors de « lire » l'image.

    - texte       : le texte extrait (chaîne, éventuellement vide)
    - ocr_utilise : True si le texte provient de l'OCR, False sinon
    """
    texte = ""
    try:
        with pdfplumber.open(chemin_pdf) as pdf:
            morceaux_de_texte = [(page.extract_text() or "") for page in pdf.pages]
        texte = "\n".join(morceaux_de_texte)
    except Exception as erreur:
        # On ne veut pas que le programme s'arrête à cause d'un seul PDF
        # illisible : on prévient et on continue avec un texte vide.
        print(f"  ! Impossible de lire le PDF ({erreur}). Texte considéré vide.")

    # Assez de texte « normal » ? Alors pas besoin d'OCR.
    if len(texte.strip()) >= SEUIL_TEXTE_OCR:
        return texte, False

    # Sinon : document probablement scanné → on tente l'OCR (si disponible).
    if autoriser_ocr and OCR_DISPONIBLE:
        texte_ocr = _ocr_pdf(chemin_pdf)
        if len(texte_ocr.strip()) > len(texte.strip()):
            return texte_ocr, True

    return texte, False


def _ocr_pdf(chemin_pdf):
    """« Lit » un PDF scanné en le passant par l'OCR (Tesseract). Retourne le texte.

    On transforme chaque page en image (via pypdfium2), puis Tesseract
    reconnaît le texte de l'image. En cas de souci, on retourne "" sans
    faire planter le programme.
    """
    morceaux = []
    try:
        pdf = pypdfium2.PdfDocument(str(chemin_pdf))
        nb_pages = min(len(pdf), OCR_PAGES_MAX)
        for i in range(nb_pages):
            page = pdf[i]
            # On rend la page en image à ~200 points par pouce (bon compromis
            # netteté / vitesse pour l'OCR). 72 = résolution PDF de base.
            image = page.render(scale=200 / 72).to_pil()
            try:
                # On demande le français en priorité.
                morceaux.append(pytesseract.image_to_string(image, lang="fra"))
            except pytesseract.TesseractError:
                # Si le pack de langue français n'est pas installé, on se
                # rabat sur la langue par défaut de Tesseract.
                morceaux.append(pytesseract.image_to_string(image))
        pdf.close()
    except Exception as erreur:
        print(f"  ! OCR impossible ({erreur}).")
        return ""
    return "\n".join(morceaux)


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
# On inclut les abréviations courantes (janv., fevr., avr., sept., dec.…).
# Ces noms ne sont cherchés qu'ENTRE deux nombres (jour et année), donc aucun
# risque qu'ils correspondent par erreur à un mot ordinaire du texte.
MOIS_FR = {
    "janvier": 1, "janv": 1, "jan": 1,
    "fevrier": 2, "fevr": 2, "fev": 2,
    "mars": 3, "mar": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7,
    "aout": 8, "aou": 8,
    "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "decembre": 12, "dec": 12,
}


def _annee_sur_4_chiffres(annee_2):
    """Transforme une année sur 2 chiffres en année sur 4 chiffres.

    Règle habituelle : 00–79 -> 2000–2079, 80–99 -> 1980–1999.
    (ex. « 26 » -> 2026, « 98 » -> 1998)
    """
    aa = int(annee_2)
    return 2000 + aa if aa <= 79 else 1900 + aa


def extraire_date(texte):
    """Cherche une date dans le texte et la retourne au format AAAA-MM-JJ.

    Formats reconnus (courants en France) :
      1) 2026-03-12                 (ISO, année en premier)
      2) 12/03/2026 ou 12-03-2026   (jour/mois/année sur 4 chiffres)
      3) 12/03/26                   (jour/mois/année sur 2 chiffres)
      4) 12 mars 2026, 12 janv. 2026 (jour mois-en-lettres année)

    On retourne la PREMIÈRE date valide trouvée (limite connue : sur un
    document il peut y en avoir plusieurs). Retourne None si aucune.
    """
    texte_normalise = sans_accents(texte)

    # --- Format 1 : 2026-03-12 (ISO) — le moins ambigu, testé en premier ---
    motif_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", texte_normalise)
    if motif_iso:
        annee, mois, jour = motif_iso.groups()
        date = _construire_date(annee, mois, jour)
        if date:
            return date

    # --- Format 2 : 12/03/2026 ou 12-03-2026 (année sur 4 chiffres) ---
    motif_numerique = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", texte_normalise
    )
    if motif_numerique:
        jour, mois, annee = motif_numerique.groups()
        date = _construire_date(annee, mois, jour)
        if date:
            return date

    # --- Format 3 : 12/03/26 (année sur 2 chiffres) ---
    motif_court = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2})\b", texte_normalise
    )
    if motif_court:
        jour, mois, annee_2 = motif_court.groups()
        date = _construire_date(_annee_sur_4_chiffres(annee_2), mois, jour)
        if date:
            return date

    # --- Format 4 : 12 mars 2026 / 12 janv. 2026 (mois en lettres) ---
    # Le point final éventuel de l'abréviation est autorisé (\.?).
    motif_lettres = re.search(
        r"\b(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})\b", texte_normalise
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
# Cœur réutilisable : analyser puis appliquer (utilisé par la ligne de
# commande ET par l'interface graphique trier_documents_gui.py)
# =============================================================================
#
# On sépare volontairement deux étapes :
#   1) ANALYSER : on regarde chaque PDF et on décide ce qu'il FAUDRAIT faire,
#      SANS toucher au disque. Chaque décision est un petit dictionnaire
#      « opération » (voir analyser_fichier).
#   2) APPLIQUER : on exécute réellement une opération (déplacement + journal).
#
# Cette séparation permet d'afficher un aperçu (simulation) avant d'agir,
# aussi bien dans le terminal que dans la fenêtre du logiciel.


def lister_pdf(base):
    """Retourne la liste triée des PDF présents dans _a_trier.

    Retourne None si le dossier _a_trier n'existe pas (cas à signaler à
    l'utilisateur), ou une liste (éventuellement vide) sinon.
    """
    dossier_a_trier = Path(base) / DOSSIER_A_TRIER
    if not dossier_a_trier.exists():
        return None
    return sorted(
        p for p in dossier_a_trier.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    )


def analyser_fichier(chemin_pdf, regles, base):
    """Analyse UN PDF et retourne l'opération prévue (sans rien déplacer).

    Le dictionnaire retourné contient tout ce qu'il faut pour :
      - afficher un aperçu à l'utilisateur,
      - puis exécuter le déplacement plus tard (via appliquer_operation).

    Clés du dictionnaire :
      source_path   : chemin actuel du fichier (Path)
      source_name   : nom actuel du fichier (str)
      classe        : True si reconnu avec assez de confiance, False sinon
      emetteur      : nom de l'émetteur reconnu (str) ou None
      categorie     : "Prive/Energie-Telecom" ... ou "_non_classe"
      confiance     : score (nombre de mots-clés trouvés)
      date          : date retenue "AAAA-MM-JJ" (None si non classé)
      date_source   : "document", "modification" ou None
      dossier_cible : dossier de destination (Path)
      nouveau_nom   : nom de fichier prévu (str ; inchangé si non classé)
      ocr           : True si le texte a été lu par OCR (document scanné)
    """
    base = Path(base)
    seuil = regles.get("reglages", {}).get("seuil_confiance_min", 2)

    # 1) Lire le texte du PDF (avec OCR en secours), puis identifier l'émetteur.
    texte, ocr_utilise = lire_texte_pdf(chemin_pdf)
    emetteur, score = identifier_emetteur(texte, regles)

    # 2) Confiance trop faible -> _non_classe, sans renommer.
    if emetteur is None or score < seuil:
        return {
            "source_path": chemin_pdf,
            "source_name": chemin_pdf.name,
            "classe": False,
            "emetteur": None,
            "categorie": DOSSIER_NON_CLASSE,
            "confiance": score,
            "date": None,
            "date_source": None,
            "dossier_cible": base / DOSSIER_NON_CLASSE,
            "nouveau_nom": chemin_pdf.name,   # on garde le nom d'origine
            "ocr": ocr_utilise,
        }

    # 3) Confiance suffisante : on trouve la date (ou repli sur date de modif).
    date = extraire_date(texte)
    date_source = "document"
    if date is None:
        date = date_de_modification(chemin_pdf)
        date_source = "modification"

    # 4) Construire la destination (dossier + nouveau nom) à partir de l'émetteur.
    categorie, dossier_cible, nouveau_nom = composer_destination(base, emetteur, date)

    return {
        "source_path": chemin_pdf,
        "source_name": chemin_pdf.name,
        "classe": True,
        "emetteur": emetteur["emetteur"],
        "categorie": categorie,
        "confiance": score,
        "date": date,
        "date_source": date_source,
        "dossier_cible": dossier_cible,
        "nouveau_nom": nouveau_nom,
        "ocr": ocr_utilise,
    }


def composer_destination(base, emetteur_dict, date):
    """Calcule (categorie, dossier_cible, nouveau_nom) pour un émetteur + une date.

    Regroupe en un seul endroit la « recette » du rangement, pour qu'elle soit
    identique partout : analyse automatique ET correction manuelle depuis la
    fenêtre. Attend une date au format 'AAAA-MM-JJ'.
    """
    annee = date[:4]
    nom_emetteur = nettoyer_pour_nom_fichier(emetteur_dict["emetteur"])
    type_doc = nettoyer_pour_nom_fichier(emetteur_dict.get("type", "document"))
    nouveau_nom = f"{date}_{nom_emetteur}_{type_doc}.pdf"

    domaine = emetteur_dict["domaine"]           # "Prive" ou "Pro"
    sous_dossier = emetteur_dict["destination"]  # ex : Energie-Telecom
    categorie = f"{domaine}/{sous_dossier}"
    dossier_cible = Path(base) / domaine / annee / sous_dossier
    return categorie, dossier_cible, nouveau_nom


def analyser_dossier(base, regles):
    """Analyse tous les PDF de _a_trier et retourne la liste des opérations.

    Ne touche à aucun fichier (simulation). Lève FileNotFoundError si le
    dossier _a_trier n'existe pas, pour que l'appelant affiche un message.
    """
    fichiers_pdf = lister_pdf(base)
    if fichiers_pdf is None:
        raise FileNotFoundError(Path(base) / DOSSIER_A_TRIER)
    return [analyser_fichier(p, regles, base) for p in fichiers_pdf]


def nouveau_lot():
    """Retourne un identifiant de lot (basé sur l'horodatage) pour un classement.

    Tous les fichiers classés « en même temps » partagent le même lot, ce qui
    permet d'annuler UNIQUEMENT ce lot-là plus tard.
    """
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def appliquer_operation(operation, chemin_journal, lot=""):
    """Exécute réellement UNE opération : déplace le fichier et journalise.

    - Crée le dossier de destination si besoin.
    - Évite toute collision de nom (suffixe _2, _3, ...) : on ne supprime
      et on n'écrase jamais rien.
    - Ajoute une ligne au journal.csv (avec l'identifiant de lot).

    Retourne le chemin final (Path) où le fichier a été déplacé.
    """
    dossier_cible = operation["dossier_cible"]

    # On calcule le chemin final au dernier moment, pour tenir compte des
    # fichiers éventuellement créés par les opérations précédentes du lot.
    destination = chemin_sans_collision(dossier_cible / operation["nouveau_nom"])

    dossier_cible.mkdir(parents=True, exist_ok=True)
    shutil.move(str(operation["source_path"]), str(destination))

    ajouter_au_journal(chemin_journal, {
        "lot": lot,
        "date_operation": datetime.datetime.now().isoformat(timespec="seconds"),
        "nom_original": operation["source_name"],
        "chemin_original": str(operation["source_path"]),
        "nouveau_nom": destination.name,
        "nouveau_chemin": str(destination),
        "categorie": operation["categorie"],
        "confiance": operation["confiance"],
    })
    return destination


def annuler_operations(base, dernier_lot_seulement=False, journaliser=print):
    """Remet en place les fichiers listés dans le journal (fonction partagée).

    Utilisée par la ligne de commande ET par la fenêtre, pour ne pas dupliquer
    cette logique délicate.

    - base                  : dossier Administration
    - dernier_lot_seulement : si True, on n'annule QUE le dernier classement
                              (le dernier « lot ») ; sinon on annule tout.
    - journaliser           : fonction appelée pour chaque message (par défaut
                              print ; la fenêtre y branche son propre journal).

    Retourne un couple (nb_remis, nb_ignores).
    On ne supprime jamais rien : si l'emplacement d'origine est déjà occupé,
    on ajoute un suffixe pour ne rien écraser.
    """
    chemin_journal = Path(base) / FICHIER_JOURNAL
    lignes = lire_journal(chemin_journal)
    if not lignes:
        return 0, 0

    # Si demandé, on ne garde que les lignes du dernier lot présent dans le
    # journal (les anciens journaux sans colonne « lot » -> lot vide "").
    if dernier_lot_seulement:
        dernier = lignes[-1].get("lot", "") or ""
        a_annuler = [lg for lg in lignes if (lg.get("lot", "") or "") == dernier]
        a_garder = [lg for lg in lignes if (lg.get("lot", "") or "") != dernier]
    else:
        a_annuler = list(lignes)
        a_garder = []

    nb_remis = 0
    # Les lignes de a_annuler qu'on n'a pas pu remettre (fichier introuvable)
    # sont conservées elles aussi, pour ne pas perdre l'information.
    non_remises = []

    # On annule dans l'ordre inverse (les opérations les plus récentes d'abord).
    for ligne in reversed(a_annuler):
        chemin_actuel = Path(ligne["nouveau_chemin"])
        chemin_origine_voulu = Path(ligne["chemin_original"])

        if not chemin_actuel.exists():
            journaliser(f"Introuvable, ignoré : {chemin_actuel}")
            non_remises.append(ligne)
            continue

        destination = chemin_sans_collision(chemin_origine_voulu)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(chemin_actuel), str(destination))
        nb_remis += 1
        if destination == chemin_origine_voulu:
            journaliser(f"Remis : {chemin_actuel.name}  ->  {destination}")
        else:
            journaliser(f"Remis (nom ajusté) : {chemin_actuel.name}  ->  {destination}")

    # On réécrit le journal avec ce qui reste (lots non concernés + échecs).
    lignes_restantes = a_garder + non_remises
    if lignes_restantes:
        with open(chemin_journal, "w", newline="", encoding="utf-8") as f:
            ecrivain = csv.DictWriter(f, fieldnames=COLONNES_JOURNAL)
            ecrivain.writeheader()
            for ligne in lignes_restantes:
                # On ne réécrit que les colonnes connues (compatibilité anciens
                # journaux qui n'avaient pas la colonne « lot »).
                ecrivain.writerow({c: ligne.get(c, "") for c in COLONNES_JOURNAL})
    else:
        chemin_journal.unlink(missing_ok=True)

    return nb_remis, len(non_remises)


# =============================================================================
# Version « ligne de commande » : afficher l'aperçu et (option) appliquer
# =============================================================================

def traiter_dossier(base, regles, mode_execute):
    """Parcourt _a_trier et classe chaque PDF (ou simule le classement).

    Paramètres :
      - base         : chemin du dossier Administration
      - regles       : les règles chargées depuis regles.yaml
      - mode_execute : True = on déplace vraiment ; False = simulation

    Cette fonction s'appuie entièrement sur le cœur réutilisable ci-dessus :
    elle se contente d'afficher les résultats dans le terminal.
    """
    base = Path(base)
    chemin_journal = base / FICHIER_JOURNAL

    # Étape 1 : analyser (aucun fichier n'est touché ici).
    try:
        operations = analyser_dossier(base, regles)
    except FileNotFoundError as chemin_manquant:
        print(f"Erreur : le dossier '{chemin_manquant}' n'existe pas.")
        print("Crée-le et déposes-y tes PDF, puis relance le script.")
        sys.exit(1)

    if not operations:
        print(f"Aucun PDF à traiter dans '{base / DOSSIER_A_TRIER}'.")
        return

    # Rappel visible du mode en cours.
    if mode_execute:
        print(">>> MODE EXECUTION : les fichiers vont être RÉELLEMENT déplacés.\n")
    else:
        print(">>> MODE SIMULATION : rien ne sera modifié (ajoute --execute pour agir).\n")

    nb_classes = 0
    nb_non_classes = 0
    # Tous les fichiers de cette exécution partagent le même « lot »,
    # ce qui permettra d'annuler uniquement ce classement-ci.
    lot = nouveau_lot()

    for operation in operations:
        print(f"Fichier : {operation['source_name']}")

        # On signale les documents lus par OCR (scans).
        if operation.get("ocr"):
            print("  (document scanné : texte lu par OCR)")

        if not operation["classe"]:
            # --- Confiance trop faible ---
            nb_non_classes += 1
            print(f"  -> Confiance faible (score {operation['confiance']}). "
                  f"Direction {DOSSIER_NON_CLASSE}.")
        else:
            # --- Reconnu ---
            nb_classes += 1
            if operation["date_source"] == "modification":
                print(f"  ! Aucune date trouvée dans le texte : utilisation de "
                      f"la date de modification du fichier ({operation['date']}).")
            print(f"  -> Émetteur : {operation['emetteur']} "
                  f"(catégorie {operation['categorie']}, "
                  f"confiance {operation['confiance']})")

        # Aperçu de la destination (nom sans le suffixe anti-collision).
        apercu = operation["dossier_cible"] / operation["nouveau_nom"]

        if mode_execute:
            destination = appliquer_operation(operation, chemin_journal, lot=lot)
            print(f"  -> Déplacé vers : {destination}")
        else:
            print(f"  -> SERAIT déplacé vers : {apercu}")
        print()

    # Résumé final.
    print("----- Résumé -----")
    print(f"  Classés        : {nb_classes}")
    print(f"  Non classés    : {nb_non_classes}")
    if not mode_execute:
        print("  (Simulation : aucun fichier n'a été modifié.)")


# =============================================================================
# Annulation : remettre les fichiers à leur place d'origine
# =============================================================================

def annuler(base, dernier_lot_seulement=False):
    """Annule les déplacements (via le journal), en affichant les messages.

    Simple habillage « terminal » autour de la fonction partagée
    annuler_operations (qui contient toute la vraie logique).
    """
    lignes = lire_journal(Path(base) / FICHIER_JOURNAL)
    if not lignes:
        print("Rien à annuler : le journal est vide ou introuvable.")
        return

    portee = "du dernier classement" if dernier_lot_seulement else "de tout le journal"
    print(f">>> Annulation {portee}.\n")

    nb_remis, nb_ignores = annuler_operations(
        base,
        dernier_lot_seulement=dernier_lot_seulement,
        journaliser=lambda msg: print(f"  {msg}"),
    )

    print(f"\n{nb_remis} fichier(s) remis.", end="")
    if nb_ignores:
        print(f" {nb_ignores} introuvable(s), conservé(s) dans le journal.")
    else:
        print()


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
    analyseur.add_argument(
        "--dernier",
        action="store_true",
        help="Avec --annuler : n'annule que le dernier classement (dernier lot).",
    )
    options = analyseur.parse_args()

    base = Path(options.base)

    # Cas 1 : on veut annuler. Pas besoin des règles pour cela.
    if options.annuler:
        annuler(base, dernier_lot_seulement=options.dernier)
        return

    # Cas 2 : classement (simulation par défaut, réel avec --execute).
    regles = charger_regles(options.regles)
    traiter_dossier(base, regles, mode_execute=options.execute)


# Cette ligne classique fait que main() ne s'exécute que si on lance
# directement ce fichier (et pas si on l'importe ailleurs).
if __name__ == "__main__":
    main()

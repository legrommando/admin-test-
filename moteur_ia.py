#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
moteur_ia.py — Classement des documents par IA LOCALE (via Ollama).

Idée : au lieu de chercher des mots-clés, on demande à un modèle d'IA qui
tourne SUR TON ORDINATEUR de « lire » le document et de dire de quoi il s'agit.

CONFIDENTIALITÉ : tout se passe en local. Le document n'est PAS envoyé sur
Internet — il est analysé par le modèle installé sur ta machine (via Ollama).

Le modèle est « à vision » : il regarde chaque page comme une image. Il lit
donc aussi bien les PDF « texte » que les PDF scannés — sans OCR séparé.

Ce module est OPTIONNEL. Si Ollama n'est pas installé ou pas démarré, la
fonction ollama_disponible() renvoie False et le logiciel retombe tout seul
sur le moteur par mots-clés (trier_documents.py). Rien ne casse.

Aucune dépendance nouvelle : on utilise urllib (inclus dans Python) pour
parler à Ollama, et pypdfium2 (déjà installé avec pdfplumber) pour convertir
les pages en images.
"""

import base64
import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import trier_documents as noyau

# Adresse locale d'Ollama (le logiciel qui fait tourner le modèle).
OLLAMA_URL_DEFAUT = "http://localhost:11434"

# Modèle par défaut : un modèle « à vision » léger et multilingue.
# Tu peux le changer dans la configuration (voir le README).
MODELE_DEFAUT = "llama3.2-vision"

# On n'analyse que les premières pages (émetteur + date sont en début de doc).
PAGES_MAX = 3

# En dessous de cette confiance (0 à 1), le document part dans _non_classe.
SEUIL_CONFIANCE_IA = 0.5


# =============================================================================
# Disponibilité d'Ollama
# =============================================================================

def ollama_disponible(base_url=OLLAMA_URL_DEFAUT, modele=MODELE_DEFAUT, timeout=3):
    """Vérifie qu'Ollama tourne et que le modèle demandé est installé.

    Retourne un couple (disponible, message) :
      - disponible : True si on peut analyser avec l'IA locale
      - message    : explication lisible (utile pour l'afficher à l'écran)
    """
    url = base_url.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8"))
    except urllib.error.URLError:
        return False, ("Ollama ne répond pas. Est-il installé et démarré ? "
                       "(voir la section « IA locale » du README)")
    except Exception as erreur:
        return False, f"Impossible de contacter Ollama : {erreur}"

    # La liste des modèles installés est dans donnees["models"].
    noms = [m.get("name", "") for m in donnees.get("models", [])]
    # Ollama nomme parfois les modèles « llama3.2-vision:latest » : on compare
    # aussi le début du nom pour être tolérant.
    installe = any(n == modele or n.startswith(modele + ":") for n in noms)
    if not installe:
        return False, (f"Le modèle « {modele} » n'est pas installé dans Ollama. "
                       f"Installe-le avec :  ollama pull {modele}")

    return True, f"IA locale prête (modèle {modele})."


# =============================================================================
# Conversion des pages PDF en images
# =============================================================================

def _pages_en_images_base64(chemin_pdf, pages_max=PAGES_MAX):
    """Transforme les premières pages d'un PDF en images PNG (encodées base64).

    Retourne une liste de chaînes base64 (une par page). Utilise pypdfium2,
    déjà présent avec pdfplumber.
    """
    import pypdfium2

    images = []
    pdf = pypdfium2.PdfDocument(str(chemin_pdf))
    try:
        nb = min(len(pdf), pages_max)
        for i in range(nb):
            page = pdf[i]
            # Rendu à ~150 points/pouce : lisible pour l'IA, sans être trop lourd.
            image = page.render(scale=150 / 72).to_pil()
            tampon = io.BytesIO()
            image.save(tampon, format="PNG")
            images.append(base64.b64encode(tampon.getvalue()).decode("ascii"))
    finally:
        pdf.close()
    return images


# =============================================================================
# Construction de la question posée au modèle
# =============================================================================

def _construire_prompt(regles):
    """Rédige les instructions envoyées au modèle, à partir de regles.yaml.

    On liste les domaines et destinations autorisés pour que le modèle range
    le document dans TES catégories (et pas dans des catégories inventées).
    """
    reglages = regles.get("reglages", {})
    prive = reglages.get("dossiers_prive", [])
    pro = reglages.get("dossiers_pro", [])

    # Quelques exemples d'émetteurs connus, pour guider le modèle.
    exemples = ", ".join(sorted({e["emetteur"] for e in regles["emetteurs"]}))

    return (
        "Tu es un assistant qui classe des documents administratifs français.\n"
        "Regarde les images (les pages d'un document PDF) et identifie :\n"
        "- l'émetteur (l'organisme qui a émis le document, ex : EDF, URSSAF, CPAM),\n"
        "- s'il s'agit d'un document Privé ou Professionnel,\n"
        "- la catégorie de rangement,\n"
        "- le type de document (ex : facture, releve, avis-impot),\n"
        "- la date du document au format AAAA-MM-JJ si elle est visible,\n"
        "- le montant principal en euros si présent,\n"
        "- la DATE LIMITE de paiement (échéance) au format AAAA-MM-JJ si présente,\n"
        "- s'il faut FAIRE quelque chose (relance, mise en demeure, à payer) : oui/non.\n\n"
        f"Catégories autorisées pour Privé : {', '.join(prive)}.\n"
        f"Catégories autorisées pour Professionnel : {', '.join(pro)}.\n"
        f"Exemples d'émetteurs déjà connus : {exemples}.\n\n"
        "Réponds UNIQUEMENT avec un objet JSON, sans texte autour, de la forme :\n"
        '{\n'
        '  "domaine": "Prive" ou "Pro",\n'
        '  "destination": une des catégories autorisées ci-dessus,\n'
        '  "emetteur": "nom court de l\'émetteur",\n'
        '  "type": "type-de-document-en-minuscules-avec-tirets",\n'
        '  "date": "AAAA-MM-JJ" ou null,\n'
        '  "montant": nombre ou null,\n'
        '  "date_echeance": "AAAA-MM-JJ" ou null,\n'
        '  "action_requise": true ou false,\n'
        '  "confiance": nombre entre 0 et 1\n'
        '}\n'
        "Si tu n'es pas sûr, mets une confiance basse. N'invente pas de catégorie."
    )


# =============================================================================
# Appel du modèle via Ollama
# =============================================================================

def _interroger_ollama(prompt, images_base64, base_url, modele, timeout=180):
    """Envoie les images + la question au modèle local et retourne le JSON lu.

    Retourne un dictionnaire (le JSON du modèle) ou lève une exception en cas
    d'échec réseau / de réponse illisible.
    """
    url = base_url.rstrip("/") + "/api/chat"
    corps = {
        "model": modele,
        "messages": [{"role": "user", "content": prompt, "images": images_base64}],
        "stream": False,
        # On demande explicitement une réponse au format JSON.
        "format": "json",
        # Température 0 = réponses stables et déterministes.
        "options": {"temperature": 0},
    }
    donnees = json.dumps(corps).encode("utf-8")
    requete = urllib.request.Request(
        url, data=donnees, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        brut = json.loads(reponse.read().decode("utf-8"))

    # Le texte produit par le modèle est dans brut["message"]["content"].
    contenu = brut.get("message", {}).get("content", "")
    return _extraire_json(contenu)


def _extraire_json(texte):
    """Extrait le premier objet JSON {...} trouvé dans une chaîne de texte.

    Même si le modèle ajoute un peu de texte autour, on récupère le JSON.
    """
    texte = texte.strip()
    # Cas simple : tout le texte est déjà du JSON.
    try:
        return json.loads(texte)
    except json.JSONDecodeError:
        pass
    # Sinon on cherche la première accolade ouvrante et la dernière fermante.
    debut = texte.find("{")
    fin = texte.rfind("}")
    if debut != -1 and fin != -1 and fin > debut:
        return json.loads(texte[debut:fin + 1])
    raise ValueError("Le modèle n'a pas renvoyé de JSON exploitable.")


# =============================================================================
# Analyse d'un fichier (même « forme » de résultat que le noyau)
# =============================================================================

def analyser_fichier_ia(chemin_pdf, regles, base, base_url=OLLAMA_URL_DEFAUT,
                        modele=MODELE_DEFAUT):
    """Analyse UN PDF avec l'IA locale et retourne une opération (sans rien déplacer).

    Le dictionnaire retourné a EXACTEMENT les mêmes clés que
    trier_documents.analyser_fichier, pour que la suite (aperçu, classement,
    annulation) fonctionne sans changement.
    """
    base = Path(base)

    # Repli sécurisé : en cas de souci (Ollama, image, JSON), on renvoie une
    # opération « non classé » plutôt que de planter tout le lot.
    def non_classe(motif):
        return {
            "source_path": chemin_pdf,
            "source_name": chemin_pdf.name,
            "classe": False,
            "emetteur": None,
            "categorie": noyau.DOSSIER_NON_CLASSE,
            "confiance": 0,
            "date": None,
            "date_source": None,
            "dossier_cible": base / noyau.DOSSIER_NON_CLASSE,
            "nouveau_nom": chemin_pdf.name,
            "ocr": False,
            "moteur": "ia",
            "motif": motif,
            "echeance": None,
            "urgence": 0,
            "urgence_label": "aucune",
        }

    try:
        images = _pages_en_images_base64(chemin_pdf)
        if not images:
            return non_classe("PDF vide ou illisible")
        prompt = _construire_prompt(regles)
        resultat = _interroger_ollama(prompt, images, base_url, modele)
    except Exception as erreur:
        return non_classe(f"IA indisponible ({erreur})")

    # --- On lit prudemment la réponse du modèle ---
    domaine = (resultat.get("domaine") or "").strip()
    destination = (resultat.get("destination") or "").strip()
    emetteur = (resultat.get("emetteur") or "").strip()
    type_doc = (resultat.get("type") or "document").strip()
    date = resultat.get("date")
    try:
        confiance = float(resultat.get("confiance", 0))
    except (TypeError, ValueError):
        confiance = 0.0

    # Vérifs : domaine valide, destination dans la liste autorisée, confiance OK.
    reglages = regles.get("reglages", {})
    destinations_ok = set(reglages.get("dossiers_prive", [])) | \
                      set(reglages.get("dossiers_pro", []))

    if (domaine not in ("Prive", "Pro") or destination not in destinations_ok
            or not emetteur or confiance < SEUIL_CONFIANCE_IA):
        op = non_classe("confiance faible ou catégorie non reconnue")
        op["confiance"] = round(confiance, 2)
        return op

    # --- Date : on valide le format ; sinon repli sur la date de modification ---
    date_source = "document"
    if not _date_valide(date):
        date = noyau.date_de_modification(chemin_pdf)
        date_source = "modification"

    # On réutilise la « recette » de rangement du noyau pour rester cohérent.
    emetteur_dict = {"emetteur": emetteur, "domaine": domaine,
                     "destination": destination, "type": type_doc}
    categorie, dossier_cible, nouveau_nom = noyau.composer_destination(
        base, emetteur_dict, date)

    # Urgence : échéance + action, telles que lues par l'IA.
    echeance = resultat.get("date_echeance")
    if not _date_valide(echeance):
        echeance = None
    action = bool(resultat.get("action_requise"))
    urgence, urgence_label = noyau.niveau_urgence(echeance, action)

    return {
        "source_path": chemin_pdf,
        "source_name": chemin_pdf.name,
        "classe": True,
        "emetteur": emetteur,
        "categorie": categorie,
        "confiance": round(confiance, 2),
        "date": date,
        "date_source": date_source,
        "dossier_cible": dossier_cible,
        "nouveau_nom": nouveau_nom,
        "ocr": False,          # l'IA vision lit l'image directement
        "moteur": "ia",
        "montant": resultat.get("montant"),
        "echeance": echeance,
        "urgence": urgence,
        "urgence_label": urgence_label,
    }


def _date_valide(valeur):
    """Retourne True si 'valeur' est une date au format AAAA-MM-JJ valide."""
    if not isinstance(valeur, str):
        return False
    import datetime
    try:
        datetime.date.fromisoformat(valeur)
        return True
    except ValueError:
        return False


def analyser_dossier_ia(base, regles, base_url=OLLAMA_URL_DEFAUT,
                        modele=MODELE_DEFAUT):
    """Analyse tous les PDF de _a_trier avec l'IA locale.

    Même comportement que trier_documents.analyser_dossier (lève
    FileNotFoundError si _a_trier n'existe pas), mais avec le moteur IA.
    """
    fichiers = noyau.lister_pdf(base)
    if fichiers is None:
        raise FileNotFoundError(Path(base) / noyau.DOSSIER_A_TRIER)
    return [analyser_fichier_ia(p, regles, base, base_url, modele) for p in fichiers]

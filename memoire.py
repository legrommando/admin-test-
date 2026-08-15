#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memoire.py — Mémoire (index) de tous les documents déjà classés.

À chaque classement, on enregistre une petite fiche dans une base de données
locale (Administration/memoire.db). Cela apporte deux choses très utiles :

  1. La RECHERCHE : retrouver instantanément un document (« toutes les factures
     EDF de 2025 », « CPAM », etc.) sans fouiller les dossiers à la main.
  2. La DÉTECTION DE DOUBLONS : reconnaître qu'un document a DÉJÀ été classé
     (même contenu), pour ne pas le ranger deux fois.

Détails techniques (pour info) :
  - On utilise SQLite, une mini base de données INCLUSE dans Python (module
    sqlite3) : aucune dépendance à installer.
  - Chaque document est identifié par une « empreinte » (hash SHA-256) calculée
    sur son contenu : deux fichiers identiques ont la même empreinte, même si
    on les a renommés.
  - Tout est prévu pour ne JAMAIS bloquer le classement : si la base pose le
    moindre problème, on ignore l'erreur et le tri continue normalement.
"""

import hashlib
import sqlite3
from pathlib import Path

import trier_documents as noyau


# Colonnes de la table (pour information).
# id, hash, nom_original, chemin, emetteur, categorie, date_doc, montant,
# lot, date_ajout


# =============================================================================
# Empreinte (hash) d'un fichier
# =============================================================================

def hash_fichier(chemin):
    """Calcule l'empreinte SHA-256 du contenu d'un fichier.

    Deux fichiers au contenu identique donnent la même empreinte. On lit par
    petits morceaux pour ne pas charger tout le fichier en mémoire.
    """
    sha = hashlib.sha256()
    with open(chemin, "rb") as f:
        for morceau in iter(lambda: f.read(65536), b""):
            sha.update(morceau)
    return sha.hexdigest()


# =============================================================================
# Connexion à la base
# =============================================================================

def _connexion(base):
    """Ouvre (et crée si besoin) la base de données de la mémoire.

    Retourne un objet connexion sqlite3, ou None si la base est inaccessible.
    """
    try:
        chemin = Path(base) / noyau.FICHIER_MEMOIRE
        chemin.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(chemin))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT,
                nom_original TEXT,
                chemin TEXT,
                emetteur TEXT,
                categorie TEXT,
                date_doc TEXT,
                montant REAL,
                lot TEXT,
                date_ajout TEXT
            )
        """)
        conn.commit()
        return conn
    except Exception:
        return None


# =============================================================================
# Enregistrer / retirer un document
# =============================================================================

def enregistrer(base, operation, destination):
    """Ajoute une fiche dans la mémoire pour un document qui vient d'être classé.

    - operation   : le dictionnaire d'opération (voir trier_documents)
    - destination : le chemin final (Path) où le fichier a été déplacé

    Ne lève jamais d'erreur : en cas de souci, on ignore simplement.
    """
    conn = _connexion(base)
    if conn is None:
        return
    try:
        import datetime
        # L'empreinte a pu être calculée pendant l'analyse ; sinon on la calcule.
        empreinte = operation.get("hash")
        if not empreinte:
            try:
                empreinte = hash_fichier(destination)
            except Exception:
                empreinte = None

        conn.execute(
            "INSERT INTO documents (hash, nom_original, chemin, emetteur, "
            "categorie, date_doc, montant, lot, date_ajout) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                empreinte,
                operation.get("source_name"),
                str(destination),
                operation.get("emetteur"),
                operation.get("categorie"),
                operation.get("date"),
                operation.get("montant"),
                operation.get("lot", ""),
                datetime.datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def retirer_par_chemin(base, chemin):
    """Supprime de la mémoire la fiche d'un document (utilisé lors d'une annulation).

    On identifie la fiche par son chemin actuel. Sans effet si la fiche n'existe
    pas. Ne lève jamais d'erreur.
    """
    conn = _connexion(base)
    if conn is None:
        return
    try:
        conn.execute("DELETE FROM documents WHERE chemin = ?", (str(chemin),))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# =============================================================================
# Détection de doublons
# =============================================================================

def hashs_connus(base):
    """Retourne l'ensemble des empreintes déjà présentes dans la mémoire.

    Sert à savoir si un nouveau document a déjà été classé auparavant.
    """
    conn = _connexion(base)
    if conn is None:
        return set()
    try:
        lignes = conn.execute(
            "SELECT hash FROM documents WHERE hash IS NOT NULL").fetchall()
        return {ligne[0] for ligne in lignes}
    except Exception:
        return set()
    finally:
        conn.close()


def annoter_doublons(base, operations):
    """Repère les doublons parmi une liste d'opérations et les marque.

    Un document est un doublon si son empreinte est :
      - déjà présente dans la mémoire (il a été classé lors d'une fois précédente), ou
      - déjà vue plus haut dans le lot en cours (deux fois le même fichier à trier).

    Pour un doublon, on modifie l'opération pour l'envoyer dans le dossier
    « _doublons » (sans renommer, sans écraser), et on pose op["doublon"] = True.
    Les autres opérations reçoivent op["doublon"] = False.

    Cette fonction modifie la liste sur place et la retourne aussi (pratique).
    """
    connus = hashs_connus(base)
    deja_vus = set()

    for op in operations:
        empreinte = None
        try:
            empreinte = hash_fichier(op["source_path"])
        except Exception:
            empreinte = None
        op["hash"] = empreinte
        op["doublon"] = False

        if empreinte and (empreinte in connus or empreinte in deja_vus):
            # C'est un doublon : direction _doublons, sans renommer.
            op["doublon"] = True
            op["classe"] = False
            op["categorie"] = noyau.DOSSIER_DOUBLONS
            op["dossier_cible"] = Path(base) / noyau.DOSSIER_DOUBLONS
            op["nouveau_nom"] = op["source_name"]
        elif empreinte:
            deja_vus.add(empreinte)

    return operations


# =============================================================================
# Recherche
# =============================================================================

def chercher(base, requete, limite=200):
    """Recherche des documents dans la mémoire.

    On coupe la requête en mots ; un document est retenu s'il contient TOUS
    les mots (dans son émetteur, sa catégorie, sa date ou son nom d'origine).
    Ex. : « EDF 2025 » trouve les documents EDF datés de 2025.

    Retourne une liste de dictionnaires (les fiches trouvées), la plus récente
    d'abord.
    """
    conn = _connexion(base)
    if conn is None:
        return []
    try:
        mots = [m for m in requete.split() if m.strip()]
        # Champs dans lesquels on cherche.
        champs = "nom_original || ' ' || IFNULL(emetteur,'') || ' ' || " \
                 "IFNULL(categorie,'') || ' ' || IFNULL(date_doc,'') || ' ' || chemin"

        clauses = []
        valeurs = []
        for mot in mots:
            clauses.append(f"({champs}) LIKE ?")
            valeurs.append(f"%{mot}%")
        ou = " AND ".join(clauses) if clauses else "1=1"

        lignes = conn.execute(
            f"SELECT nom_original, emetteur, categorie, date_doc, montant, chemin "
            f"FROM documents WHERE {ou} ORDER BY id DESC LIMIT ?",
            valeurs + [limite],
        ).fetchall()

        return [
            {
                "nom_original": l[0], "emetteur": l[1], "categorie": l[2],
                "date_doc": l[3], "montant": l[4], "chemin": l[5],
            }
            for l in lignes
        ]
    except Exception:
        return []
    finally:
        conn.close()

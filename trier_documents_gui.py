#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trier_documents_gui.py — Interface graphique (fenêtre) pour le tri des PDF.

C'est la version « logiciel » de trier_documents.py : au lieu de taper des
commandes, tu utilises une fenêtre avec des boutons.

Comment ça marche, en 3 boutons :
    1. « Analyser »  : le logiciel regarde les PDF de _a_trier et affiche,
                       dans un tableau, ce qu'il compte faire. RIEN n'est
                       déplacé à cette étape (c'est un aperçu).
    2. « Classer »   : après confirmation, il déplace réellement les fichiers
                       vers Prive/... et Pro/..., et note tout dans le journal.
    3. « Annuler »   : remet les fichiers du dernier classement à leur place.

Lancement :
    python trier_documents.py            (ça, c'est la version terminal)
    python trier_documents_gui.py        (ça, c'est cette fenêtre)

Aucune dépendance en plus : tkinter (la fenêtre) est inclus dans Python.
Le logiciel réutilise toute la logique de tri de trier_documents.py :
il n'y a donc qu'une seule « vraie » façon de classer, partagée par les deux.
"""

import queue          # pour transmettre le résultat du thread à la fenêtre
import threading      # pour analyser les PDF sans « geler » la fenêtre
from pathlib import Path

# --- Import de tkinter (la bibliothèque de fenêtres, incluse dans Python) ---
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
except ImportError:
    # Cas très rare : certaines installations Python minimales n'ont pas tkinter.
    print("Erreur : le module 'tkinter' n'est pas disponible dans ton Python.")
    print("Sous Windows/Mac, réinstalle Python depuis python.org (tkinter est inclus).")
    print("Sous Linux, installe le paquet 'python3-tk'.")
    raise SystemExit(1)

# --- Import de notre logique de tri (le fichier voisin trier_documents.py) ---
# On lui donne le petit surnom « noyau » (le cœur du programme).
import trier_documents as noyau


class Application(tk.Tk):
    """La fenêtre principale du logiciel.

    Hérite de tk.Tk, la fenêtre de base de tkinter. Tout le contenu
    (boutons, tableau, journal) est créé dans __init__.
    """

    def __init__(self):
        super().__init__()

        # --- Réglages de la fenêtre ---
        self.title("Tri des documents administratifs")
        self.geometry("980x640")     # largeur x hauteur au démarrage
        self.minsize(820, 520)       # taille minimale pour rester lisible

        # --- Variables internes ---
        # Dossier de travail par défaut : « Administration » à côté du script.
        dossier_du_script = Path(__file__).resolve().parent
        self.base = dossier_du_script / noyau.DOSSIER_RACINE
        self.chemin_regles = dossier_du_script / noyau.FICHIER_REGLES

        # Les règles de classement (chargées au démarrage).
        self.regles = None
        # La liste des opérations calculées par la dernière analyse.
        self.operations = []
        # File d'attente utilisée pour recevoir, sans risque, le résultat
        # de l'analyse faite dans le thread (voir _lancer_analyse).
        self.file_resultats = queue.Queue()

        # On construit l'interface, puis on charge les règles.
        self._construire_interface()
        self._charger_regles_au_demarrage()

    # -------------------------------------------------------------------------
    # Construction de l'interface (les différentes zones de la fenêtre)
    # -------------------------------------------------------------------------
    def _construire_interface(self):
        """Crée et dispose tous les éléments visuels de la fenêtre."""

        # ----- Zone du haut : choix du dossier -----
        cadre_haut = ttk.Frame(self, padding=10)
        cadre_haut.pack(fill="x")

        ttk.Label(cadre_haut, text="Dossier de travail :").pack(side="left")

        # Un champ (non modifiable à la main) qui montre le dossier choisi.
        self.var_dossier = tk.StringVar(value=str(self.base))
        champ = ttk.Entry(cadre_haut, textvariable=self.var_dossier, state="readonly")
        champ.pack(side="left", fill="x", expand=True, padx=8)

        ttk.Button(cadre_haut, text="Changer…",
                   command=self._choisir_dossier).pack(side="left")

        # ----- Zone des boutons d'action -----
        cadre_actions = ttk.Frame(self, padding=(10, 0, 10, 10))
        cadre_actions.pack(fill="x")

        self.bouton_analyser = ttk.Button(
            cadre_actions, text="1. Analyser (aperçu)",
            command=self._lancer_analyse)
        self.bouton_analyser.pack(side="left")

        self.bouton_classer = ttk.Button(
            cadre_actions, text="2. Classer les fichiers ▶",
            command=self._classer, state="disabled")
        self.bouton_classer.pack(side="left", padx=8)

        self.bouton_annuler = ttk.Button(
            cadre_actions, text="↩ Annuler le dernier classement",
            command=self._annuler)
        self.bouton_annuler.pack(side="left")

        ttk.Button(cadre_actions, text="Ouvrir le dossier",
                   command=self._ouvrir_dossier).pack(side="right")

        # ----- Zone centrale : le tableau des résultats -----
        cadre_tableau = ttk.Frame(self, padding=(10, 0, 10, 10))
        cadre_tableau.pack(fill="both", expand=True)

        colonnes = ("fichier", "emetteur", "categorie", "date", "confiance", "nouveau_nom")
        self.tableau = ttk.Treeview(
            cadre_tableau, columns=colonnes, show="headings", height=12)

        # Titre et largeur de chaque colonne.
        self.tableau.heading("fichier", text="Fichier d'origine")
        self.tableau.heading("emetteur", text="Émetteur")
        self.tableau.heading("categorie", text="Rangé dans")
        self.tableau.heading("date", text="Date")
        self.tableau.heading("confiance", text="Confiance")
        self.tableau.heading("nouveau_nom", text="Nouveau nom")

        self.tableau.column("fichier", width=180)
        self.tableau.column("emetteur", width=90, anchor="center")
        self.tableau.column("categorie", width=150)
        self.tableau.column("date", width=90, anchor="center")
        self.tableau.column("confiance", width=75, anchor="center")
        self.tableau.column("nouveau_nom", width=280)

        # Une couleur douce pour repérer d'un coup d'œil les documents
        # non reconnus (qui iront dans _non_classe sans être renommés).
        self.tableau.tag_configure("non_classe", background="#ffe9d6")

        # Barre de défilement verticale pour le tableau.
        barre = ttk.Scrollbar(cadre_tableau, orient="vertical",
                              command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=barre.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        barre.pack(side="right", fill="y")

        # ----- Zone du bas : journal des messages + barre d'état -----
        cadre_bas = ttk.Frame(self, padding=(10, 0, 10, 10))
        cadre_bas.pack(fill="both")

        ttk.Label(cadre_bas, text="Messages :").pack(anchor="w")
        self.zone_messages = scrolledtext.ScrolledText(
            cadre_bas, height=7, state="disabled", wrap="word")
        self.zone_messages.pack(fill="both", expand=True)

        # Barre d'état tout en bas (une petite ligne d'information).
        self.var_etat = tk.StringVar(value="Prêt.")
        ttk.Label(self, textvariable=self.var_etat, relief="sunken",
                  anchor="w", padding=4).pack(fill="x", side="bottom")

    # -------------------------------------------------------------------------
    # Petites aides pour écrire des messages et changer l'état
    # -------------------------------------------------------------------------
    def _message(self, texte):
        """Ajoute une ligne dans la zone de messages du bas."""
        self.zone_messages.configure(state="normal")
        self.zone_messages.insert("end", texte + "\n")
        self.zone_messages.see("end")          # on fait défiler vers le bas
        self.zone_messages.configure(state="disabled")

    def _etat(self, texte):
        """Change le texte de la barre d'état (tout en bas)."""
        self.var_etat.set(texte)

    # -------------------------------------------------------------------------
    # Chargement des règles de classement
    # -------------------------------------------------------------------------
    def _charger_regles_au_demarrage(self):
        """Lit regles.yaml au lancement et prévient si un souci survient."""
        try:
            self.regles = noyau.charger_regles(self.chemin_regles)
            nb = len(self.regles.get("emetteurs", []))
            self._message(f"Règles chargées : {nb} émetteurs connus "
                          f"(fichier {self.chemin_regles.name}).")
        except SystemExit:
            # charger_regles fait sys.exit en cas d'erreur : on l'intercepte
            # pour afficher une vraie boîte de dialogue au lieu de fermer.
            self.regles = None
            messagebox.showerror(
                "Fichier de règles manquant",
                f"Impossible de lire '{self.chemin_regles}'.\n\n"
                "Vérifie que le fichier regles.yaml est bien à côté du logiciel.")

    # -------------------------------------------------------------------------
    # Bouton « Changer… » : choisir un autre dossier de travail
    # -------------------------------------------------------------------------
    def _choisir_dossier(self):
        """Ouvre une boîte pour choisir le dossier « Administration »."""
        dossier = filedialog.askdirectory(
            title="Choisis le dossier Administration (celui qui contient _a_trier)",
            initialdir=str(self.base.parent if self.base.exists() else Path.home()))
        if dossier:
            self.base = Path(dossier)
            self.var_dossier.set(str(self.base))
            self._vider_tableau()
            self.bouton_classer.configure(state="disabled")
            self._message(f"Dossier de travail : {self.base}")

    # -------------------------------------------------------------------------
    # Bouton « Ouvrir le dossier » : ouvrir l'explorateur de fichiers
    # -------------------------------------------------------------------------
    def _ouvrir_dossier(self):
        """Ouvre le dossier de travail dans l'explorateur du système."""
        if not self.base.exists():
            messagebox.showinfo(
                "Dossier absent",
                f"Le dossier n'existe pas encore :\n{self.base}\n\n"
                "Il sera créé automatiquement au premier classement.")
            return

        import os
        import subprocess
        import sys as _sys
        try:
            if _sys.platform.startswith("win"):
                os.startfile(str(self.base))          # Windows
            elif _sys.platform == "darwin":
                subprocess.Popen(["open", str(self.base)])   # macOS
            else:
                subprocess.Popen(["xdg-open", str(self.base)])  # Linux
        except Exception as erreur:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le dossier :\n{erreur}")

    # -------------------------------------------------------------------------
    # Bouton « Analyser » : calcule l'aperçu (dans un fil séparé)
    # -------------------------------------------------------------------------
    def _lancer_analyse(self):
        """Démarre l'analyse des PDF sans bloquer la fenêtre.

        Lire des PDF peut prendre quelques secondes. Pour que la fenêtre ne
        se fige pas, on fait ce travail dans un « thread » (fil d'exécution
        séparé), puis on revient mettre à jour l'affichage.
        """
        if self.regles is None:
            messagebox.showerror(
                "Règles manquantes",
                "Les règles de classement ne sont pas chargées. "
                "Vérifie le fichier regles.yaml.")
            return

        # On désactive les boutons pendant l'analyse pour éviter les
        # doubles-clics et les actions concurrentes.
        self._verrouiller_boutons(True)
        self._vider_tableau()
        self._etat("Analyse en cours…")
        self._message("Analyse des PDF de _a_trier…")

        # Le travail lourd part dans un thread. Le thread NE touche JAMAIS à
        # l'interface : il dépose seulement son résultat dans la file d'attente.
        # C'est la fenêtre (fil principal) qui viendra le récupérer.
        fil = threading.Thread(target=self._analyse_en_arriere_plan, daemon=True)
        fil.start()

        # On vérifie régulièrement (toutes les 100 ms) si le résultat est prêt.
        self.after(100, self._verifier_file_analyse)

    def _analyse_en_arriere_plan(self):
        """Fait l'analyse (dans le thread). Ne touche PAS à l'écran.

        Le résultat est déposé dans self.file_resultats sous la forme d'un
        couple (type, donnée) :
          ("ok", operations)        analyse réussie
          ("dossier_absent", None)  le dossier _a_trier n'existe pas
          ("erreur", message)       autre erreur inattendue
        """
        try:
            operations = noyau.analyser_dossier(self.base, self.regles)
            self.file_resultats.put(("ok", operations))
        except FileNotFoundError:
            self.file_resultats.put(("dossier_absent", None))
        except Exception as erreur:
            self.file_resultats.put(("erreur", str(erreur)))

    def _verifier_file_analyse(self):
        """Regarde si le thread a fini ; si oui, met à jour l'affichage.

        Cette fonction s'exécute dans le fil principal (c'est elle qui a le
        droit de toucher à l'interface). Tant qu'il n'y a rien dans la file,
        elle se replanifie toute seule.
        """
        try:
            type_resultat, donnee = self.file_resultats.get_nowait()
        except queue.Empty:
            # Pas encore prêt : on repasse dans 100 ms.
            self.after(100, self._verifier_file_analyse)
            return

        if type_resultat == "ok":
            self._analyse_terminee(donnee)
        elif type_resultat == "dossier_absent":
            self._analyse_echouee_dossier()
        else:
            self._analyse_echouee_autre(donnee)

    def _analyse_terminee(self, operations):
        """Reçoit la liste des opérations et remplit le tableau."""
        self.operations = operations
        self._verrouiller_boutons(False)

        if not operations:
            self._etat("Aucun PDF à traiter.")
            self._message(f"Aucun PDF trouvé dans {self.base / noyau.DOSSIER_A_TRIER}.")
            self.bouton_classer.configure(state="disabled")
            return

        nb_classes = 0
        nb_non_classes = 0

        for op in operations:
            if op["classe"]:
                nb_classes += 1
                emetteur = op["emetteur"]
                categorie = op["categorie"]
                date = op["date"]
                nouveau_nom = op["nouveau_nom"]
                # Petit rappel si la date vient de la date de modification.
                if op["date_source"] == "modification":
                    date = f"{date} (fichier)"
                etiquettes = ()
            else:
                nb_non_classes += 1
                emetteur = "—"
                categorie = "_non_classe (à vérifier)"
                date = "—"
                nouveau_nom = "(nom inchangé)"
                etiquettes = ("non_classe",)

            self.tableau.insert(
                "", "end",
                values=(op["source_name"], emetteur, categorie, date,
                        op["confiance"], nouveau_nom),
                tags=etiquettes)

        self._etat(f"Aperçu prêt : {nb_classes} à classer, "
                   f"{nb_non_classes} non classé(s). Rien n'a été déplacé.")
        self._message(f"Analyse terminée : {nb_classes} reconnu(s), "
                      f"{nb_non_classes} non classé(s).")

        # On n'active « Classer » que s'il y a au moins un fichier à traiter.
        self.bouton_classer.configure(state="normal")

    def _analyse_echouee_dossier(self):
        """Cas : le dossier _a_trier n'existe pas."""
        self._verrouiller_boutons(False)
        self._etat("Dossier _a_trier introuvable.")
        chemin = self.base / noyau.DOSSIER_A_TRIER
        self._message(f"Le dossier {chemin} n'existe pas.")
        messagebox.showwarning(
            "Dossier à trier introuvable",
            f"Le dossier suivant n'existe pas :\n{chemin}\n\n"
            "Crée-le et déposes-y tes PDF, ou choisis un autre dossier "
            "de travail avec le bouton « Changer… ».")

    def _analyse_echouee_autre(self, message):
        """Cas : une autre erreur inattendue pendant l'analyse."""
        self._verrouiller_boutons(False)
        self._etat("Erreur pendant l'analyse.")
        self._message(f"Erreur : {message}")
        messagebox.showerror("Erreur pendant l'analyse", message)

    # -------------------------------------------------------------------------
    # Bouton « Classer » : déplace réellement les fichiers (après confirmation)
    # -------------------------------------------------------------------------
    def _classer(self):
        """Applique réellement les opérations affichées, après confirmation."""
        if not self.operations:
            return

        nb = len(self.operations)
        # Demande de confirmation : c'est la seule étape qui modifie le disque.
        confirmer = messagebox.askyesno(
            "Confirmer le classement",
            f"{nb} fichier(s) vont être déplacés et renommés selon l'aperçu.\n\n"
            "Aucun fichier ne sera supprimé ni écrasé, et tu pourras tout "
            "annuler ensuite.\n\nContinuer ?")
        if not confirmer:
            self._message("Classement annulé par l'utilisateur (rien n'a bougé).")
            return

        chemin_journal = self.base / noyau.FICHIER_JOURNAL
        nb_ok = 0
        try:
            for op in self.operations:
                destination = noyau.appliquer_operation(op, chemin_journal)
                nb_ok += 1
                self._message(f"Déplacé : {op['source_name']}  →  {destination}")
        except Exception as erreur:
            self._message(f"Erreur pendant le classement : {erreur}")
            messagebox.showerror(
                "Erreur pendant le classement",
                f"Une erreur est survenue :\n{erreur}\n\n"
                f"{nb_ok} fichier(s) ont déjà été déplacés (voir le journal).")

        self._etat(f"Classement terminé : {nb_ok} fichier(s) déplacé(s).")
        messagebox.showinfo(
            "Classement terminé",
            f"{nb_ok} fichier(s) ont été classés.\n\n"
            "Tu peux tout remettre en place avec « Annuler le dernier classement ».")

        # L'aperçu n'est plus valable (les fichiers ont bougé) : on nettoie.
        self._vider_tableau()
        self.operations = []
        self.bouton_classer.configure(state="disabled")

    # -------------------------------------------------------------------------
    # Bouton « Annuler » : remet les fichiers à leur place via le journal
    # -------------------------------------------------------------------------
    def _annuler(self):
        """Relit le journal et remet chaque fichier à son emplacement d'origine."""
        chemin_journal = self.base / noyau.FICHIER_JOURNAL
        lignes = noyau.lire_journal(chemin_journal)

        if not lignes:
            messagebox.showinfo(
                "Rien à annuler",
                "Le journal est vide ou introuvable : il n'y a rien à annuler.")
            return

        confirmer = messagebox.askyesno(
            "Confirmer l'annulation",
            f"Remettre {len(lignes)} fichier(s) à leur emplacement d'origine ?")
        if not confirmer:
            return

        import shutil
        nb_remis = 0
        lignes_restantes = []

        # On annule dans l'ordre inverse (les plus récentes d'abord).
        for ligne in reversed(lignes):
            chemin_actuel = Path(ligne["nouveau_chemin"])
            chemin_origine_voulu = Path(ligne["chemin_original"])

            if not chemin_actuel.exists():
                self._message(f"Introuvable, ignoré : {chemin_actuel}")
                lignes_restantes.append(ligne)
                continue

            destination = noyau.chemin_sans_collision(chemin_origine_voulu)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(chemin_actuel), str(destination))
            nb_remis += 1
            self._message(f"Remis : {chemin_actuel.name}  →  {destination}")

        # On met à jour (ou on supprime) le journal selon ce qui a été remis.
        if lignes_restantes:
            import csv
            with open(chemin_journal, "w", newline="", encoding="utf-8") as f:
                ecrivain = csv.DictWriter(f, fieldnames=noyau.COLONNES_JOURNAL)
                ecrivain.writeheader()
                for ligne in reversed(lignes_restantes):
                    ecrivain.writerow(ligne)
        else:
            chemin_journal.unlink(missing_ok=True)

        self._etat(f"Annulation terminée : {nb_remis} fichier(s) remis.")
        messagebox.showinfo(
            "Annulation terminée",
            f"{nb_remis} fichier(s) ont été remis à leur place.")
        self._vider_tableau()
        self.operations = []
        self.bouton_classer.configure(state="disabled")

    # -------------------------------------------------------------------------
    # Utilitaires d'interface
    # -------------------------------------------------------------------------
    def _vider_tableau(self):
        """Efface toutes les lignes du tableau."""
        for ligne in self.tableau.get_children():
            self.tableau.delete(ligne)

    def _verrouiller_boutons(self, verrouille):
        """Active ou désactive les boutons pendant un traitement long."""
        etat = "disabled" if verrouille else "normal"
        self.bouton_analyser.configure(state=etat)
        self.bouton_annuler.configure(state=etat)
        # Le bouton « Classer » reste géré séparément (selon l'aperçu).


def main():
    """Point d'entrée : crée la fenêtre et lance la boucle graphique."""
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()

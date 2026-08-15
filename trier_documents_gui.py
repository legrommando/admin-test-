#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trier_documents_gui.py — Interface graphique moderne pour le tri des PDF.

C'est la version « logiciel » de trier_documents.py : au lieu de taper des
commandes, tu utilises une fenêtre avec des boutons.

Comment ça marche, en 3 boutons :
    1. « Analyser » : le logiciel regarde les PDF de _a_trier et affiche,
                      dans un tableau, ce qu'il compte faire. RIEN n'est
                      déplacé à cette étape (c'est un aperçu).
    2. « Classer »  : après confirmation, il déplace réellement les fichiers
                      vers Prive/... et Pro/..., et note tout dans le journal.
    3. « Annuler »  : remet les fichiers du dernier classement à leur place.

Lancement :
    python trier_documents_gui.py        (ou double-clic sur Lancer_le_logiciel.bat)

Apparence :
    Le logiciel utilise un thème moderne (sv-ttk, style Windows 11) s'il est
    installé, avec un mode clair/sombre. S'il n'est pas là, il fonctionne
    quand même avec l'apparence classique : rien ne bloque.

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
    from tkinter import font as tkfont
except ImportError:
    print("Erreur : le module 'tkinter' n'est pas disponible dans ton Python.")
    print("Sous Windows/Mac, réinstalle Python depuis python.org (tkinter est inclus).")
    print("Sous Linux, installe le paquet 'python3-tk'.")
    raise SystemExit(1)

# --- Thème moderne (facultatif) : sv-ttk donne un look « Windows 11 » ---
# On l'importe dans un try : s'il n'est pas installé, le logiciel marche
# quand même avec l'apparence classique de tkinter.
try:
    import sv_ttk
    THEME_MODERNE_DISPO = True
except ImportError:
    THEME_MODERNE_DISPO = False

# --- Import de notre logique de tri (le fichier voisin trier_documents.py) ---
import trier_documents as noyau


# Couleurs utilisées pour les petits repères de couleur (identiques en clair
# et en sombre, car ce sont des couleurs « d'accent » bien contrastées).
COULEUR_OK = "#2e9e5b"        # vert : documents reconnus / succès
COULEUR_ATTENTION = "#d98a00"  # orange : documents à vérifier
COULEUR_DISCRET = "#8a8a8a"    # gris : informations secondaires


class Application(tk.Tk):
    """La fenêtre principale du logiciel (version moderne)."""

    def __init__(self):
        super().__init__()

        # --- Réglages de la fenêtre ---
        self.title("Tri des documents administratifs")
        self.geometry("1040x720")
        self.minsize(880, 600)

        # --- Variables internes ---
        dossier_du_script = Path(__file__).resolve().parent
        self.base = dossier_du_script / noyau.DOSSIER_RACINE
        self.chemin_regles = dossier_du_script / noyau.FICHIER_REGLES

        self.regles = None
        self.operations = []
        self.file_resultats = queue.Queue()
        self.theme_sombre = False   # on démarre en clair

        # --- Apparence : polices et thème ---
        self._preparer_apparence()

        # --- Construction de l'interface, puis chargement des règles ---
        self._construire_interface()
        self._charger_regles_au_demarrage()

    # -------------------------------------------------------------------------
    # Apparence (thème + polices + styles du tableau)
    # -------------------------------------------------------------------------
    def _preparer_apparence(self):
        """Applique le thème moderne et prépare les polices."""
        # Police de base : Segoe UI sous Windows (moderne), sinon la police
        # par défaut. On règle une taille un peu plus grande pour le confort.
        familles = set(tkfont.families())
        famille = "Segoe UI" if "Segoe UI" in familles else \
                  ("Helvetica" if "Helvetica" in familles else "TkDefaultFont")

        self.police_base = (famille, 10)
        self.police_titre = (famille, 18, "bold")
        self.police_sous_titre = (famille, 10)
        self.police_bouton = (famille, 10)
        self.police_tableau = (famille, 10)
        self.police_entete = (famille, 10, "bold")

        # Police par défaut de toute la fenêtre.
        try:
            defaut = tkfont.nametofont("TkDefaultFont")
            defaut.configure(family=famille, size=10)
            self.option_add("*Font", defaut)
        except tk.TclError:
            pass

        # Thème moderne si disponible.
        if THEME_MODERNE_DISPO:
            sv_ttk.set_theme("light")

        # Réglages fins du tableau (lignes plus hautes, en-têtes en gras).
        style = ttk.Style(self)
        style.configure("Treeview", rowheight=30, font=self.police_tableau)
        style.configure("Treeview.Heading", font=self.police_entete)

    def _basculer_theme(self):
        """Passe du mode clair au mode sombre (et inversement)."""
        if not THEME_MODERNE_DISPO:
            messagebox.showinfo(
                "Thème",
                "Le mode sombre nécessite le composant « sv-ttk ».\n"
                "Il s'installe tout seul via Lancer_le_logiciel.bat.")
            return
        self.theme_sombre = not self.theme_sombre
        sv_ttk.set_theme("dark" if self.theme_sombre else "light")
        self.bouton_theme.configure(text="☀  Clair" if self.theme_sombre else "🌙  Sombre")
        # La couleur du zébrage (une ligne sur deux) dépend du mode clair/sombre :
        # on la remet à jour pour éviter une bande claire en mode sombre.
        self.tableau.tag_configure("impair", background=self._couleur_zebre())

    # -------------------------------------------------------------------------
    # Construction de l'interface
    # -------------------------------------------------------------------------
    def _construire_interface(self):
        """Crée et dispose tous les éléments visuels de la fenêtre."""

        # ============ EN-TÊTE : titre + bouton thème ============
        entete = ttk.Frame(self, padding=(20, 16, 20, 8))
        entete.pack(fill="x")

        bloc_titre = ttk.Frame(entete)
        bloc_titre.pack(side="left")
        ttk.Label(bloc_titre, text="🗂  Tri des documents administratifs",
                  font=self.police_titre).pack(anchor="w")
        ttk.Label(bloc_titre,
                  text="Range automatiquement tes PDF dans Privé / Pro.",
                  font=self.police_sous_titre,
                  foreground=COULEUR_DISCRET).pack(anchor="w")

        self.bouton_theme = ttk.Button(entete, text="🌙  Sombre", width=10,
                                       command=self._basculer_theme)
        self.bouton_theme.pack(side="right", anchor="n")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20)

        # ============ LIGNE : dossier de travail ============
        cadre_dossier = ttk.Frame(self, padding=(20, 12, 20, 4))
        cadre_dossier.pack(fill="x")

        ttk.Label(cadre_dossier, text="Dossier de travail",
                  foreground=COULEUR_DISCRET).pack(anchor="w")

        ligne_dossier = ttk.Frame(cadre_dossier)
        ligne_dossier.pack(fill="x", pady=(4, 0))

        self.var_dossier = tk.StringVar(value=str(self.base))
        ttk.Entry(ligne_dossier, textvariable=self.var_dossier,
                  state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(ligne_dossier, text="📂  Changer…", width=12,
                   command=self._choisir_dossier).pack(side="left", padx=(8, 0))
        ttk.Button(ligne_dossier, text="📁  Ouvrir", width=10,
                   command=self._ouvrir_dossier).pack(side="left", padx=(8, 0))

        # ============ LIGNE : les 3 actions ============
        cadre_actions = ttk.Frame(self, padding=(20, 10, 20, 6))
        cadre_actions.pack(fill="x")

        # Le bouton « Analyser » est mis en avant (style Accent si dispo).
        style_accent = "Accent.TButton" if THEME_MODERNE_DISPO else "TButton"

        self.bouton_analyser = ttk.Button(
            cadre_actions, text="①  🔍  Analyser (aperçu)",
            style=style_accent, command=self._lancer_analyse)
        self.bouton_analyser.pack(side="left", ipady=4)

        self.bouton_classer = ttk.Button(
            cadre_actions, text="②  📦  Classer les fichiers",
            command=self._classer, state="disabled")
        self.bouton_classer.pack(side="left", padx=10, ipady=4)

        self.bouton_annuler = ttk.Button(
            cadre_actions, text="↩  Annuler le dernier classement",
            command=self._annuler)
        self.bouton_annuler.pack(side="left", ipady=4)

        # ============ TABLEAU des résultats ============
        cadre_tableau = ttk.Frame(self, padding=(20, 6, 20, 6))
        cadre_tableau.pack(fill="both", expand=True)

        colonnes = ("statut", "fichier", "emetteur", "categorie", "date", "nouveau_nom")
        self.tableau = ttk.Treeview(cadre_tableau, columns=colonnes,
                                    show="headings", height=12)

        self.tableau.heading("statut", text="")
        self.tableau.heading("fichier", text="Fichier d'origine")
        self.tableau.heading("emetteur", text="Émetteur")
        self.tableau.heading("categorie", text="Rangé dans")
        self.tableau.heading("date", text="Date")
        self.tableau.heading("nouveau_nom", text="Nouveau nom")

        self.tableau.column("statut", width=40, anchor="center", stretch=False)
        self.tableau.column("fichier", width=200)
        self.tableau.column("emetteur", width=100, anchor="center")
        self.tableau.column("categorie", width=170)
        self.tableau.column("date", width=100, anchor="center")
        self.tableau.column("nouveau_nom", width=300)

        # Couleurs des lignes : reconnu (normal), à vérifier (orange), et
        # une teinte alternée discrète pour lire plus facilement (zébrage).
        self.tableau.tag_configure("nonclasse", foreground=COULEUR_ATTENTION)
        self.tableau.tag_configure("impair", background=self._couleur_zebre())

        barre = ttk.Scrollbar(cadre_tableau, orient="vertical",
                             command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=barre.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        barre.pack(side="right", fill="y")

        # ============ JOURNAL des messages ============
        cadre_bas = ttk.Frame(self, padding=(20, 0, 20, 6))
        cadre_bas.pack(fill="both")

        ttk.Label(cadre_bas, text="Journal",
                  foreground=COULEUR_DISCRET).pack(anchor="w")
        self.zone_messages = scrolledtext.ScrolledText(
            cadre_bas, height=6, state="disabled", wrap="word",
            font=(self.police_base[0], 9), relief="flat", borderwidth=1)
        self.zone_messages.pack(fill="both", expand=True, pady=(4, 0))

        # ============ BARRE D'ÉTAT ============
        self.var_etat = tk.StringVar(value="Prêt.")
        self.label_etat = ttk.Label(self, textvariable=self.var_etat,
                                    anchor="w", padding=(20, 6))
        self.label_etat.pack(fill="x", side="bottom")

    def _couleur_zebre(self):
        """Teinte discrète pour une ligne sur deux (selon clair/sombre)."""
        return "#2a2a2a" if self.theme_sombre else "#f3f4f6"

    # -------------------------------------------------------------------------
    # Aides : messages, état
    # -------------------------------------------------------------------------
    def _message(self, texte):
        """Ajoute une ligne dans le journal du bas."""
        self.zone_messages.configure(state="normal")
        self.zone_messages.insert("end", texte + "\n")
        self.zone_messages.see("end")
        self.zone_messages.configure(state="disabled")

    def _etat(self, texte, couleur=None):
        """Change le texte (et éventuellement la couleur) de la barre d'état."""
        self.var_etat.set(texte)
        self.label_etat.configure(foreground=couleur if couleur else "")

    # -------------------------------------------------------------------------
    # Chargement des règles
    # -------------------------------------------------------------------------
    def _charger_regles_au_demarrage(self):
        """Lit regles.yaml au lancement et prévient si un souci survient."""
        try:
            self.regles = noyau.charger_regles(self.chemin_regles)
            nb = len(self.regles.get("emetteurs", []))
            self._message(f"Règles chargées : {nb} émetteurs connus "
                          f"(fichier {self.chemin_regles.name}).")
            if not THEME_MODERNE_DISPO:
                self._message("Astuce : installe « sv-ttk » pour un thème "
                              "moderne + mode sombre (le .bat le fait tout seul).")
        except SystemExit:
            self.regles = None
            messagebox.showerror(
                "Fichier de règles manquant",
                f"Impossible de lire '{self.chemin_regles}'.\n\n"
                "Vérifie que le fichier regles.yaml est bien à côté du logiciel.")

    # -------------------------------------------------------------------------
    # Bouton « Changer… »
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
    # Bouton « Ouvrir »
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
                os.startfile(str(self.base))
            elif _sys.platform == "darwin":
                subprocess.Popen(["open", str(self.base)])
            else:
                subprocess.Popen(["xdg-open", str(self.base)])
        except Exception as erreur:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le dossier :\n{erreur}")

    # -------------------------------------------------------------------------
    # Bouton « Analyser » (dans un fil séparé)
    # -------------------------------------------------------------------------
    def _lancer_analyse(self):
        """Démarre l'analyse des PDF sans bloquer la fenêtre."""
        if self.regles is None:
            messagebox.showerror(
                "Règles manquantes",
                "Les règles de classement ne sont pas chargées. "
                "Vérifie le fichier regles.yaml.")
            return

        self._verrouiller_boutons(True)
        self._vider_tableau()
        self._etat("Analyse en cours…")
        self._message("Analyse des PDF de _a_trier…")

        fil = threading.Thread(target=self._analyse_en_arriere_plan, daemon=True)
        fil.start()
        self.after(100, self._verifier_file_analyse)

    def _analyse_en_arriere_plan(self):
        """Fait l'analyse (dans le thread). Ne touche PAS à l'écran."""
        try:
            operations = noyau.analyser_dossier(self.base, self.regles)
            self.file_resultats.put(("ok", operations))
        except FileNotFoundError:
            self.file_resultats.put(("dossier_absent", None))
        except Exception as erreur:
            self.file_resultats.put(("erreur", str(erreur)))

    def _verifier_file_analyse(self):
        """Regarde si le thread a fini ; si oui, met à jour l'affichage."""
        try:
            type_resultat, donnee = self.file_resultats.get_nowait()
        except queue.Empty:
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
            self._etat("Aucun PDF à traiter.", COULEUR_DISCRET)
            self._message(f"Aucun PDF trouvé dans {self.base / noyau.DOSSIER_A_TRIER}.")
            self.bouton_classer.configure(state="disabled")
            return

        nb_classes = 0
        nb_non_classes = 0

        for index, op in enumerate(operations):
            # Zébrage : une ligne sur deux reçoit une teinte discrète.
            tags = ["impair"] if index % 2 else []

            if op["classe"]:
                nb_classes += 1
                statut = "✅"
                emetteur = op["emetteur"]
                categorie = op["categorie"]
                date = op["date"]
                if op["date_source"] == "modification":
                    date = f"{date} *"   # l'étoile = date issue du fichier
                nouveau_nom = op["nouveau_nom"]
            else:
                nb_non_classes += 1
                tags.append("nonclasse")
                statut = "⚠"
                emetteur = "—"
                categorie = "_non_classe (à vérifier)"
                date = "—"
                nouveau_nom = "(nom inchangé)"

            self.tableau.insert(
                "", "end",
                values=(statut, op["source_name"], emetteur, categorie,
                        date, nouveau_nom),
                tags=tuple(tags))

        self._etat(
            f"Aperçu prêt : {nb_classes} à classer, {nb_non_classes} à vérifier. "
            f"Rien n'a été déplacé.",
            COULEUR_OK if nb_non_classes == 0 else COULEUR_ATTENTION)
        self._message(f"Analyse terminée : {nb_classes} reconnu(s), "
                      f"{nb_non_classes} non classé(s).")
        self.bouton_classer.configure(state="normal")

    def _analyse_echouee_dossier(self):
        """Cas : le dossier _a_trier n'existe pas."""
        self._verrouiller_boutons(False)
        self._etat("Dossier _a_trier introuvable.", COULEUR_ATTENTION)
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
        self._etat("Erreur pendant l'analyse.", COULEUR_ATTENTION)
        self._message(f"Erreur : {message}")
        messagebox.showerror("Erreur pendant l'analyse", message)

    # -------------------------------------------------------------------------
    # Bouton « Classer »
    # -------------------------------------------------------------------------
    def _classer(self):
        """Applique réellement les opérations affichées, après confirmation."""
        if not self.operations:
            return

        nb = len(self.operations)
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

        self._etat(f"Classement terminé : {nb_ok} fichier(s) déplacé(s).", COULEUR_OK)
        messagebox.showinfo(
            "Classement terminé",
            f"{nb_ok} fichier(s) ont été classés.\n\n"
            "Tu peux tout remettre en place avec « Annuler le dernier classement ».")

        self._vider_tableau()
        self.operations = []
        self.bouton_classer.configure(state="disabled")

    # -------------------------------------------------------------------------
    # Bouton « Annuler »
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

        if lignes_restantes:
            import csv
            with open(chemin_journal, "w", newline="", encoding="utf-8") as f:
                ecrivain = csv.DictWriter(f, fieldnames=noyau.COLONNES_JOURNAL)
                ecrivain.writeheader()
                for ligne in reversed(lignes_restantes):
                    ecrivain.writerow(ligne)
        else:
            chemin_journal.unlink(missing_ok=True)

        self._etat(f"Annulation terminée : {nb_remis} fichier(s) remis.", COULEUR_OK)
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


def main():
    """Point d'entrée : crée la fenêtre et lance la boucle graphique."""
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()

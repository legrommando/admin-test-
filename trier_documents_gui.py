#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trier_documents_gui.py — Interface graphique moderne pour le tri des PDF.

C'est la version « logiciel » de trier_documents.py : au lieu de taper des
commandes, tu utilises une fenêtre avec des boutons.

Fonctionnement en 3 boutons :
    1. « Analyser » : regarde les PDF de _a_trier et affiche, dans un tableau,
                      ce qu'il compte faire. RIEN n'est déplacé (aperçu).
    2. « Classer »  : après confirmation, déplace réellement les fichiers.
    3. « Annuler »  : remet les fichiers du DERNIER classement à leur place.

Petits plus de confort :
    - Double-clic sur une ligne pour CORRIGER à la main la catégorie.
    - Bouton « Ajouter des PDF… » (et glisser-déposer si disponible).
    - Barre de progression pendant l'analyse.
    - Mémorise le dernier dossier utilisé et le thème (clair/sombre).
    - Lit aussi les documents scannés si l'OCR est installé.

Lancement :
    python trier_documents_gui.py     (ou double-clic sur Lancer_le_logiciel.bat)

Le logiciel réutilise toute la logique de tri de trier_documents.py :
il n'y a donc qu'une seule « vraie » façon de classer, partagée par les deux.
"""

import json           # pour mémoriser les préférences (dossier, thème)
import queue          # pour transmettre le résultat du thread à la fenêtre
import shutil         # pour copier les PDF ajoutés
import sys            # pour détecter le mode « exécutable » (PyInstaller)
import threading      # pour analyser les PDF sans « geler » la fenêtre
from pathlib import Path


def dossier_application():
    """Retourne le dossier où « vit » le logiciel.

    - En mode normal (script Python) : le dossier du fichier .py.
    - En mode exécutable (.exe fabriqué avec PyInstaller) : le dossier où se
      trouve le .exe (et non le dossier temporaire d'extraction), pour que le
      logiciel trouve regles.yaml et crée Administration/ juste à côté de lui.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

# --- tkinter (inclus dans Python) ---
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    from tkinter import font as tkfont
except ImportError:
    print("Erreur : le module 'tkinter' n'est pas disponible dans ton Python.")
    print("Sous Windows/Mac, réinstalle Python depuis python.org (tkinter est inclus).")
    print("Sous Linux, installe le paquet 'python3-tk'.")
    raise SystemExit(1)

# --- Thème moderne (facultatif) : sv-ttk = look « Windows 11 » ---
try:
    import sv_ttk
    THEME_MODERNE_DISPO = True
except ImportError:
    THEME_MODERNE_DISPO = False

# --- Glisser-déposer (facultatif) : tkinterdnd2 ---
try:
    import tkinterdnd2
    DND_DISPO = True
except ImportError:
    DND_DISPO = False

# --- Notre logique de tri (le fichier voisin trier_documents.py) ---
import trier_documents as noyau

# --- Moteur IA locale (facultatif) : classement par IA sur ta machine ---
# Importé dans un try : si le fichier manque, la fenêtre marche quand même
# avec le seul moteur par mots-clés.
try:
    import moteur_ia
    MOTEUR_IA_DISPO = True
except Exception:
    MOTEUR_IA_DISPO = False


# Couleurs d'accent (identiques en clair et en sombre, bien contrastées).
COULEUR_OK = "#2e9e5b"         # vert : reconnu / succès
COULEUR_ATTENTION = "#d98a00"  # orange : à vérifier
COULEUR_DISCRET = "#8a8a8a"    # gris : informations secondaires

# Fichier où l'on mémorise les préférences (dans le dossier personnel).
FICHIER_CONFIG = Path.home() / ".trier_documents.json"


class Application(tk.Tk):
    """La fenêtre principale du logiciel."""

    def __init__(self):
        super().__init__()

        self.title("Tri des documents administratifs")
        self.geometry("1060x760")
        self.minsize(900, 620)

        # --- Emplacements par défaut (à côté du logiciel / de l'exe) ---
        dossier = dossier_application()
        self.base = dossier / noyau.DOSSIER_RACINE
        self.chemin_regles = dossier / noyau.FICHIER_REGLES

        # --- État interne ---
        self.regles = None
        self.operations = []
        self.file_resultats = queue.Queue()
        self.theme_sombre = False
        # Moteur d'analyse : "regles" (mots-clés) ou "ia" (IA locale).
        self.moteur = "regles"

        # --- Préférences mémorisées (dossier, thème) ---
        self._charger_config()

        # --- Apparence, interface, règles ---
        self._preparer_apparence()
        self._construire_interface()
        self._activer_glisser_deposer()
        self._charger_regles_au_demarrage()

        # Sauvegarde des préférences à la fermeture.
        self.protocol("WM_DELETE_WINDOW", self._a_la_fermeture)

    # =========================================================================
    # Préférences (mémorisation dossier + thème)
    # =========================================================================
    def _charger_config(self):
        """Lit le fichier de préférences s'il existe (sans jamais planter)."""
        try:
            if FICHIER_CONFIG.exists():
                donnees = json.loads(FICHIER_CONFIG.read_text(encoding="utf-8"))
                dossier = donnees.get("dernier_dossier")
                if dossier and Path(dossier).exists():
                    self.base = Path(dossier)
                self.theme_sombre = bool(donnees.get("theme_sombre", False))
                if donnees.get("moteur") in ("regles", "ia"):
                    self.moteur = donnees["moteur"]
        except Exception:
            pass  # des préférences illisibles ne doivent pas bloquer le logiciel

    def _sauver_config(self):
        """Écrit les préférences actuelles (sans jamais planter)."""
        try:
            FICHIER_CONFIG.write_text(json.dumps({
                "dernier_dossier": str(self.base),
                "theme_sombre": self.theme_sombre,
                "moteur": self.moteur,
            }, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _a_la_fermeture(self):
        """Appelé quand on ferme la fenêtre : on mémorise puis on quitte."""
        self._sauver_config()
        self.destroy()

    # =========================================================================
    # Apparence
    # =========================================================================
    def _preparer_apparence(self):
        """Applique le thème moderne et prépare les polices."""
        familles = set(tkfont.families())
        famille = "Segoe UI" if "Segoe UI" in familles else \
                  ("Helvetica" if "Helvetica" in familles else "TkDefaultFont")

        self.police_titre = (famille, 18, "bold")
        self.police_sous_titre = (famille, 10)
        self.police_tableau = (famille, 10)
        self.police_entete = (famille, 10, "bold")
        self.police_journal = (famille, 9)

        try:
            defaut = tkfont.nametofont("TkDefaultFont")
            defaut.configure(family=famille, size=10)
            self.option_add("*Font", defaut)
        except tk.TclError:
            pass

        if THEME_MODERNE_DISPO:
            sv_ttk.set_theme("dark" if self.theme_sombre else "light")

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
        self.tableau.tag_configure("impair", background=self._couleur_zebre())
        self._sauver_config()

    def _couleur_zebre(self):
        """Teinte discrète pour une ligne sur deux (selon clair/sombre)."""
        return "#2a2a2a" if self.theme_sombre else "#f3f4f6"

    def _changer_moteur(self, evenement=None):
        """Change le moteur d'analyse (mots-clés ou IA locale) et le mémorise."""
        self.moteur = self._libelles_moteur.get(self.var_moteur.get(), "regles")
        self._sauver_config()
        if self.moteur == "ia":
            if not MOTEUR_IA_DISPO:
                self._message("Le moteur IA locale n'est pas disponible "
                              "(fichier moteur_ia.py manquant).")
                return
            # On informe tout de suite si Ollama répond ou non.
            disponible, message = moteur_ia.ollama_disponible()
            self._message("IA locale : " + message)
            if not disponible:
                self._message("→ Sans Ollama, l'analyse retombera sur les mots-clés.")
        else:
            self._message("Méthode d'analyse : mots-clés (hors-ligne).")

    # =========================================================================
    # Construction de l'interface
    # =========================================================================
    def _construire_interface(self):
        """Crée et dispose tous les éléments visuels."""

        # ---------- EN-TÊTE ----------
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

        self.bouton_theme = ttk.Button(
            entete, text="☀  Clair" if self.theme_sombre else "🌙  Sombre",
            width=10, command=self._basculer_theme)
        self.bouton_theme.pack(side="right", anchor="n")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20)

        # ---------- DOSSIER DE TRAVAIL ----------
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

        # ---------- CHOIX DU MOTEUR D'ANALYSE ----------
        cadre_moteur = ttk.Frame(self, padding=(20, 8, 20, 0))
        cadre_moteur.pack(fill="x")
        ttk.Label(cadre_moteur, text="Méthode d'analyse :").pack(side="left")

        # Libellés affichés <-> codes internes.
        self._libelles_moteur = {
            "Mots-clés (rapide, hors-ligne)": "regles",
            "IA locale (privée, lit les scans)": "ia",
        }
        libelle_actuel = next(lib for lib, code in self._libelles_moteur.items()
                              if code == self.moteur)
        self.var_moteur = tk.StringVar(value=libelle_actuel)
        liste_moteur = ttk.Combobox(
            cadre_moteur, textvariable=self.var_moteur, state="readonly", width=34,
            values=list(self._libelles_moteur.keys()))
        liste_moteur.pack(side="left", padx=(8, 0))
        liste_moteur.bind("<<ComboboxSelected>>", self._changer_moteur)

        # ---------- ACTIONS ----------
        cadre_actions = ttk.Frame(self, padding=(20, 10, 20, 4))
        cadre_actions.pack(fill="x")

        style_accent = "Accent.TButton" if THEME_MODERNE_DISPO else "TButton"

        self.bouton_ajouter = ttk.Button(
            cadre_actions, text="➕  Ajouter des PDF…",
            command=self._ajouter_pdf)
        self.bouton_ajouter.pack(side="left", ipady=4)

        self.bouton_analyser = ttk.Button(
            cadre_actions, text="①  🔍  Analyser (aperçu)",
            style=style_accent, command=self._lancer_analyse)
        self.bouton_analyser.pack(side="left", padx=(10, 0), ipady=4)

        self.bouton_classer = ttk.Button(
            cadre_actions, text="②  📦  Classer les fichiers",
            command=self._classer, state="disabled")
        self.bouton_classer.pack(side="left", padx=10, ipady=4)

        self.bouton_annuler = ttk.Button(
            cadre_actions, text="↩  Annuler le dernier classement",
            command=self._annuler)
        self.bouton_annuler.pack(side="left", ipady=4)

        # Petite aide sous les boutons.
        ttk.Label(self,
                  text="Astuce : double-clique sur une ligne pour corriger sa catégorie.",
                  foreground=COULEUR_DISCRET,
                  padding=(20, 0, 20, 0)).pack(anchor="w")

        # ---------- BARRE DE PROGRESSION (cachée au repos) ----------
        self.cadre_progres = ttk.Frame(self, padding=(20, 4, 20, 0))
        self.var_progres = tk.DoubleVar(value=0)
        self.barre_progres = ttk.Progressbar(
            self.cadre_progres, variable=self.var_progres, maximum=100)
        self.barre_progres.pack(fill="x")
        # (on n'affiche cadre_progres que pendant l'analyse)

        # ---------- TABLEAU ----------
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
        self.tableau.column("statut", width=44, anchor="center", stretch=False)
        self.tableau.column("fichier", width=210)
        self.tableau.column("emetteur", width=100, anchor="center")
        self.tableau.column("categorie", width=170)
        self.tableau.column("date", width=105, anchor="center")
        self.tableau.column("nouveau_nom", width=300)

        self.tableau.tag_configure("nonclasse", foreground=COULEUR_ATTENTION)
        self.tableau.tag_configure("impair", background=self._couleur_zebre())

        barre = ttk.Scrollbar(cadre_tableau, orient="vertical",
                             command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=barre.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        barre.pack(side="right", fill="y")

        # Double-clic sur une ligne = corriger la catégorie.
        self.tableau.bind("<Double-1>", self._corriger_ligne)

        # ---------- JOURNAL ----------
        cadre_bas = ttk.Frame(self, padding=(20, 0, 20, 6))
        cadre_bas.pack(fill="both")
        ttk.Label(cadre_bas, text="Journal",
                  foreground=COULEUR_DISCRET).pack(anchor="w")
        self.zone_messages = scrolledtext.ScrolledText(
            cadre_bas, height=6, state="disabled", wrap="word",
            font=self.police_journal, relief="flat", borderwidth=1)
        self.zone_messages.pack(fill="both", expand=True, pady=(4, 0))

        # ---------- BARRE D'ÉTAT ----------
        self.var_etat = tk.StringVar(value="Prêt.")
        self.label_etat = ttk.Label(self, textvariable=self.var_etat,
                                    anchor="w", padding=(20, 6))
        self.label_etat.pack(fill="x", side="bottom")

    # =========================================================================
    # Glisser-déposer (facultatif)
    # =========================================================================
    def _activer_glisser_deposer(self):
        """Autorise le dépôt de fichiers PDF sur le tableau, si disponible."""
        if not DND_DISPO:
            return
        try:
            self.tableau.drop_target_register(tkinterdnd2.DND_FILES)
            self.tableau.dnd_bind("<<Drop>>", self._sur_depot)
        except Exception:
            pass  # si le glisser-déposer ne s'initialise pas, on l'ignore

    def _sur_depot(self, evenement):
        """Reçoit les fichiers glissés dans la fenêtre et les ajoute à _a_trier."""
        # evenement.data est une chaîne du style "{C:\a b\x.pdf} C:\y.pdf"
        chemins = self.tk.splitlist(evenement.data)
        pdfs = [c for c in chemins if c.lower().endswith(".pdf")]
        if pdfs:
            self._copier_vers_a_trier(pdfs)

    # =========================================================================
    # Aides : messages, état
    # =========================================================================
    def _message(self, texte):
        self.zone_messages.configure(state="normal")
        self.zone_messages.insert("end", texte + "\n")
        self.zone_messages.see("end")
        self.zone_messages.configure(state="disabled")

    def _etat(self, texte, couleur=None):
        self.var_etat.set(texte)
        self.label_etat.configure(foreground=couleur if couleur else "")

    # =========================================================================
    # Chargement des règles
    # =========================================================================
    def _charger_regles_au_demarrage(self):
        try:
            self.regles = noyau.charger_regles(self.chemin_regles)
            nb = len(self.regles.get("emetteurs", []))
            self._message(f"Règles chargées : {nb} émetteurs connus "
                          f"(fichier {self.chemin_regles.name}).")
            if noyau.OCR_DISPONIBLE:
                self._message("OCR disponible : les documents scannés seront lus.")
            else:
                self._message("OCR non disponible : les scans ne seront pas lus "
                              "(voir le README pour l'activer).")
            if not THEME_MODERNE_DISPO:
                self._message("Astuce : installe « sv-ttk » pour un thème "
                              "moderne + mode sombre (le .bat le fait tout seul).")
        except SystemExit:
            self.regles = None
            messagebox.showerror(
                "Fichier de règles manquant",
                f"Impossible de lire '{self.chemin_regles}'.\n\n"
                "Vérifie que le fichier regles.yaml est bien à côté du logiciel.")

    # =========================================================================
    # Dossier de travail
    # =========================================================================
    def _choisir_dossier(self):
        dossier = filedialog.askdirectory(
            title="Choisis le dossier Administration (celui qui contient _a_trier)",
            initialdir=str(self.base.parent if self.base.exists() else Path.home()))
        if dossier:
            self.base = Path(dossier)
            self.var_dossier.set(str(self.base))
            self._vider_tableau()
            self.operations = []
            self.bouton_classer.configure(state="disabled")
            self._sauver_config()
            self._message(f"Dossier de travail : {self.base}")

    def _ouvrir_dossier(self):
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

    # =========================================================================
    # Ajouter des PDF (bouton + glisser-déposer)
    # =========================================================================
    def _ajouter_pdf(self):
        """Choisit des PDF et les copie dans _a_trier, puis relance l'analyse."""
        fichiers = filedialog.askopenfilenames(
            title="Choisir des PDF à ajouter",
            filetypes=[("Fichiers PDF", "*.pdf")])
        if fichiers:
            self._copier_vers_a_trier(fichiers)

    def _copier_vers_a_trier(self, chemins):
        """Copie une liste de PDF dans _a_trier (sans écraser), puis analyse."""
        cible = self.base / noyau.DOSSIER_A_TRIER
        cible.mkdir(parents=True, exist_ok=True)
        nb = 0
        for chemin in chemins:
            source = Path(chemin)
            if source.suffix.lower() != ".pdf" or not source.is_file():
                continue
            destination = noyau.chemin_sans_collision(cible / source.name)
            try:
                shutil.copy2(str(source), str(destination))
                nb += 1
            except Exception as erreur:
                self._message(f"Impossible de copier {source.name} : {erreur}")
        if nb:
            self._message(f"{nb} PDF ajouté(s) dans _a_trier.")
            self._lancer_analyse()
        else:
            self._message("Aucun PDF valide à ajouter.")

    # =========================================================================
    # Analyse (thread + barre de progression)
    # =========================================================================
    def _lancer_analyse(self):
        if self.regles is None:
            messagebox.showerror(
                "Règles manquantes",
                "Les règles de classement ne sont pas chargées. "
                "Vérifie le fichier regles.yaml.")
            return

        self._verrouiller_boutons(True)
        self._vider_tableau()
        self.operations = []
        self._etat("Analyse en cours…")
        self._message("Analyse des PDF de _a_trier…")

        # Affiche la barre de progression.
        self.var_progres.set(0)
        self.cadre_progres.pack(fill="x")

        fil = threading.Thread(target=self._analyse_en_arriere_plan, daemon=True)
        fil.start()
        self.after(100, self._verifier_file_analyse)

    def _analyse_en_arriere_plan(self):
        """Analyse fichier par fichier (dans le thread), en signalant l'avancement."""
        try:
            fichiers = noyau.lister_pdf(self.base)
            if fichiers is None:
                self.file_resultats.put(("dossier_absent", None))
                return

            # On choisit le moteur : IA locale si demandé ET disponible,
            # sinon mots-clés (repli automatique, jamais de blocage).
            analyser = self._choisir_analyseur()

            operations = []
            total = len(fichiers)
            for i, chemin in enumerate(fichiers, start=1):
                operations.append(analyser(chemin))
                self.file_resultats.put(("progres", (i, total, chemin.name)))
            self.file_resultats.put(("ok", operations))
        except Exception as erreur:
            self.file_resultats.put(("erreur", str(erreur)))

    def _choisir_analyseur(self):
        """Retourne la fonction d'analyse d'UN fichier selon le moteur choisi.

        Toutes deux renvoient la même « forme » d'opération, donc la suite du
        programme ne change pas. En cas d'IA indisponible, on retombe sur les
        mots-clés en le signalant dans le journal.
        """
        if self.moteur == "ia" and MOTEUR_IA_DISPO:
            disponible, message = moteur_ia.ollama_disponible()
            if disponible:
                self.file_resultats.put(("info", "Analyse par IA locale : " + message))
                return lambda p: moteur_ia.analyser_fichier_ia(p, self.regles, self.base)
            self.file_resultats.put(
                ("info", "IA locale indisponible, repli sur les mots-clés : " + message))
        return lambda p: noyau.analyser_fichier(p, self.regles, self.base)

    def _verifier_file_analyse(self):
        """Récupère (dans le fil principal) ce que le thread a déposé."""
        try:
            while True:
                type_resultat, donnee = self.file_resultats.get_nowait()
                if type_resultat == "progres":
                    i, total, nom = donnee
                    self.var_progres.set(100 * i / total if total else 0)
                    self._etat(f"Analyse : {i}/{total} — {nom}")
                elif type_resultat == "info":
                    # Message d'information (ex : moteur utilisé) ; on continue.
                    self._message(donnee)
                elif type_resultat == "ok":
                    self._analyse_terminee(donnee)
                    return
                elif type_resultat == "dossier_absent":
                    self._analyse_echouee_dossier()
                    return
                else:
                    self._analyse_echouee_autre(donnee)
                    return
        except queue.Empty:
            self.after(100, self._verifier_file_analyse)

    def _analyse_terminee(self, operations):
        self.operations = operations
        self._verrouiller_boutons(False)
        self.cadre_progres.pack_forget()   # on cache la barre de progression

        if not operations:
            self._etat("Aucun PDF à traiter.", COULEUR_DISCRET)
            self._message(f"Aucun PDF trouvé dans {self.base / noyau.DOSSIER_A_TRIER}.")
            self.bouton_classer.configure(state="disabled")
            return

        self._remplir_tableau()

        nb_classes = sum(1 for op in operations if op["classe"])
        nb_non = len(operations) - nb_classes
        nb_ocr = sum(1 for op in operations if op.get("ocr"))

        message_ocr = f" (dont {nb_ocr} scan(s) lus par OCR)" if nb_ocr else ""
        self._etat(
            f"Aperçu prêt : {nb_classes} à classer, {nb_non} à vérifier. "
            f"Rien n'a été déplacé.",
            COULEUR_OK if nb_non == 0 else COULEUR_ATTENTION)
        self._message(f"Analyse terminée : {nb_classes} reconnu(s), "
                      f"{nb_non} non classé(s){message_ocr}.")
        self.bouton_classer.configure(state="normal")

    def _analyse_echouee_dossier(self):
        self._verrouiller_boutons(False)
        self.cadre_progres.pack_forget()
        self._etat("Dossier _a_trier introuvable.", COULEUR_ATTENTION)
        chemin = self.base / noyau.DOSSIER_A_TRIER
        self._message(f"Le dossier {chemin} n'existe pas.")
        messagebox.showwarning(
            "Dossier à trier introuvable",
            f"Le dossier suivant n'existe pas :\n{chemin}\n\n"
            "Utilise « ➕ Ajouter des PDF… », ou choisis un autre dossier "
            "de travail avec « Changer… ».")

    def _analyse_echouee_autre(self, message):
        self._verrouiller_boutons(False)
        self.cadre_progres.pack_forget()
        self._etat("Erreur pendant l'analyse.", COULEUR_ATTENTION)
        self._message(f"Erreur : {message}")
        messagebox.showerror("Erreur pendant l'analyse", message)

    # =========================================================================
    # Remplissage du tableau (à partir de self.operations)
    # =========================================================================
    def _remplir_tableau(self):
        """Reconstruit tout le tableau depuis self.operations.

        Passer par cette fonction unique permet de rafraîchir facilement le
        tableau après une correction manuelle.
        """
        self._vider_tableau()
        for index, op in enumerate(self.operations):
            tags = ["impair"] if index % 2 else []
            prefixe_ocr = "🔍 " if op.get("ocr") else ""

            if op["classe"]:
                statut = "✅"
                emetteur = op["emetteur"]
                categorie = op["categorie"]
                date = op["date"] + (" *" if op["date_source"] == "modification" else "")
                nouveau_nom = op["nouveau_nom"]
            else:
                tags.append("nonclasse")
                statut = "⚠"
                emetteur = "—"
                categorie = "_non_classe (à vérifier)"
                date = "—"
                nouveau_nom = "(nom inchangé)"

            # iid = index, pour retrouver l'opération lors d'un double-clic.
            self.tableau.insert(
                "", "end", iid=str(index),
                values=(statut, prefixe_ocr + op["source_name"], emetteur,
                        categorie, date, nouveau_nom),
                tags=tuple(tags))

    # =========================================================================
    # Correction manuelle (double-clic sur une ligne)
    # =========================================================================
    def _corriger_ligne(self, evenement):
        """Ouvre une petite fenêtre pour réattribuer la catégorie d'un document."""
        selection = self.tableau.identify_row(evenement.y)
        if not selection:
            return
        index = int(selection)
        op = self.operations[index]
        DialogueCorrection(self, op, self.regles, self._appliquer_correction)

    def _appliquer_correction(self, index_op, emetteur_dict, date):
        """Reçoit le choix de l'utilisateur et met à jour l'opération concernée."""
        # On retrouve l'opération par sa position (l'iid du tableau).
        op = self.operations[index_op]

        if emetteur_dict is None:
            # L'utilisateur a choisi « Non classé » : on remet en _non_classe.
            op.update({
                "classe": False,
                "emetteur": None,
                "categorie": noyau.DOSSIER_NON_CLASSE,
                "date": None,
                "date_source": None,
                "dossier_cible": self.base / noyau.DOSSIER_NON_CLASSE,
                "nouveau_nom": op["source_name"],
            })
        else:
            categorie, dossier_cible, nouveau_nom = noyau.composer_destination(
                self.base, emetteur_dict, date)
            op.update({
                "classe": True,
                "emetteur": emetteur_dict["emetteur"],
                "categorie": categorie,
                "date": date,
                "date_source": "manuel",
                "dossier_cible": dossier_cible,
                "nouveau_nom": nouveau_nom,
            })
        self._remplir_tableau()
        self.tableau.selection_set(str(index_op))
        self._message(f"Correction : {op['source_name']} → {op['categorie']}.")

    def _index_de_operation(self, op):
        """Retrouve la position d'une opération dans self.operations."""
        for i, autre in enumerate(self.operations):
            if autre is op:
                return i
        return -1

    # =========================================================================
    # Classer
    # =========================================================================
    def _classer(self):
        if not self.operations:
            return
        nb = len(self.operations)
        if not messagebox.askyesno(
                "Confirmer le classement",
                f"{nb} fichier(s) vont être déplacés et renommés selon l'aperçu.\n\n"
                "Aucun fichier ne sera supprimé ni écrasé, et tu pourras tout "
                "annuler ensuite.\n\nContinuer ?"):
            self._message("Classement annulé par l'utilisateur (rien n'a bougé).")
            return

        chemin_journal = self.base / noyau.FICHIER_JOURNAL
        lot = noyau.nouveau_lot()   # tout ce classement partage le même lot
        nb_ok = 0
        try:
            for op in self.operations:
                destination = noyau.appliquer_operation(op, chemin_journal, lot=lot)
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

    # =========================================================================
    # Annuler (le dernier lot), via la fonction partagée du noyau
    # =========================================================================
    def _annuler(self):
        lignes = noyau.lire_journal(self.base / noyau.FICHIER_JOURNAL)
        if not lignes:
            messagebox.showinfo(
                "Rien à annuler",
                "Le journal est vide ou introuvable : il n'y a rien à annuler.")
            return

        if not messagebox.askyesno(
                "Confirmer l'annulation",
                "Remettre les fichiers du DERNIER classement à leur "
                "emplacement d'origine ?"):
            return

        nb_remis, nb_ignores = noyau.annuler_operations(
            self.base, dernier_lot_seulement=True, journaliser=self._message)

        self._etat(f"Annulation terminée : {nb_remis} fichier(s) remis.", COULEUR_OK)
        messagebox.showinfo(
            "Annulation terminée",
            f"{nb_remis} fichier(s) ont été remis à leur place." +
            (f"\n{nb_ignores} introuvable(s)." if nb_ignores else ""))
        self._vider_tableau()
        self.operations = []
        self.bouton_classer.configure(state="disabled")

    # =========================================================================
    # Utilitaires
    # =========================================================================
    def _vider_tableau(self):
        for ligne in self.tableau.get_children():
            self.tableau.delete(ligne)

    def _verrouiller_boutons(self, verrouille):
        etat = "disabled" if verrouille else "normal"
        self.bouton_analyser.configure(state=etat)
        self.bouton_annuler.configure(state=etat)
        self.bouton_ajouter.configure(state=etat)


class DialogueCorrection(tk.Toplevel):
    """Petite fenêtre pour corriger à la main la catégorie d'un document."""

    def __init__(self, parent, operation, regles, callback):
        super().__init__(parent)
        self.parent = parent
        self.operation = operation
        self.regles = regles
        self.callback = callback

        self.title("Corriger le classement")
        self.transient(parent)     # reste au-dessus de la fenêtre principale
        self.resizable(False, False)
        self.grab_set()            # fenêtre « modale » (on doit répondre)

        cadre = ttk.Frame(self, padding=16)
        cadre.pack(fill="both", expand=True)

        ttk.Label(cadre, text=f"Fichier : {operation['source_name']}",
                  font=(parent.police_sous_titre[0], 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        # --- Choix de l'émetteur / catégorie ---
        ttk.Label(cadre, text="Ranger comme :").grid(row=1, column=0, sticky="w")

        # On construit la liste : « Non classé » + tous les émetteurs connus.
        self.choix = ["(Non classé — laisser dans _non_classe)"]
        self.emetteurs = [None]
        for em in regles["emetteurs"]:
            self.choix.append(f"{em['emetteur']}  →  {em['domaine']}/{em['destination']}")
            self.emetteurs.append(em)

        self.var_choix = tk.StringVar()
        # Présélection : l'émetteur actuel si le document est déjà classé.
        index_actuel = 0
        if operation["classe"]:
            for i, em in enumerate(self.emetteurs):
                if em and em["emetteur"] == operation["emetteur"]:
                    index_actuel = i
                    break
        self.var_choix.set(self.choix[index_actuel])

        liste = ttk.Combobox(cadre, textvariable=self.var_choix,
                             values=self.choix, state="readonly", width=44)
        liste.grid(row=1, column=1, sticky="we", padx=(8, 0), pady=4)

        # --- Date ---
        ttk.Label(cadre, text="Date (AAAA-MM-JJ) :").grid(row=2, column=0, sticky="w")
        date_defaut = operation["date"] or noyau.date_de_modification(operation["source_path"])
        self.var_date = tk.StringVar(value=date_defaut)
        ttk.Entry(cadre, textvariable=self.var_date, width=16).grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        # --- Boutons ---
        barre = ttk.Frame(cadre)
        barre.grid(row=3, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(barre, text="Annuler", command=self.destroy).pack(side="right")
        style_ok = "Accent.TButton" if THEME_MODERNE_DISPO else "TButton"
        ttk.Button(barre, text="Valider", style=style_ok,
                   command=self._valider).pack(side="right", padx=(0, 8))

        liste.focus_set()

    def _valider(self):
        """Vérifie la saisie puis renvoie le choix à la fenêtre principale."""
        position = self.choix.index(self.var_choix.get())
        emetteur_dict = self.emetteurs[position]

        date = self.var_date.get().strip()
        if emetteur_dict is not None:
            # On vérifie que la date est bien au format AAAA-MM-JJ.
            import datetime
            try:
                datetime.date.fromisoformat(date)
            except ValueError:
                messagebox.showwarning(
                    "Date invalide",
                    "La date doit être au format AAAA-MM-JJ (ex. 2026-03-12).",
                    parent=self)
                return

        index_op = self.parent._index_de_operation(self.operation)
        self.callback(index_op, emetteur_dict, date)
        self.destroy()


def main():
    """Point d'entrée : crée la fenêtre et lance la boucle graphique."""
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()

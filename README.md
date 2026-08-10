# admin-test- — Tri automatique de documents administratifs

Petit outil en Python qui range automatiquement tes PDF administratifs.
Tu déposes tes documents en vrac dans un dossier, le script les **identifie**,
les **renomme** et les **classe** dans une arborescence Privé / Pro.

> **Sécurité d'abord :** rien n'est jamais modifié sans que tu voies d'abord
> un **aperçu**, et le logiciel ne supprime ni n'écrase jamais aucun fichier.

Il y a **deux façons** de s'en servir, au choix :

- 🪟 **Le logiciel (fenêtre)** — le plus simple : des boutons, un tableau,
  aucune commande à taper. → voir la section 2.
- ⌨️ **La ligne de commande** — pour les habitués du terminal ou les
  traitements automatisés. → voir la section 3.

Les deux utilisent exactement le même moteur de classement.

---

## 1. Installation

Il te faut Python 3 (≥ 3.8). Installe ensuite les dépendances :

```bash
pip install -r requirements.txt
```

> Sous **Windows** et **macOS**, l'installateur officiel de python.org inclut
> déjà tout ce qu'il faut pour la fenêtre (tkinter) — rien de plus à installer.
> Sous **Linux**, si la fenêtre ne s'ouvre pas, installe le paquet
> `python3-tk` (ex. `sudo apt install python3-tk`).

## 2. Le logiciel (fenêtre) — le plus simple

### Lancer

- **Windows** : double-clique sur **`Lancer_le_logiciel.bat`**.
  (ou, dans un terminal : `python trier_documents_gui.py`)
- **macOS / Linux** : `python3 trier_documents_gui.py`

### Utiliser, en 3 boutons

1. **« 1. Analyser (aperçu) »** — le logiciel lit les PDF de `_a_trier` et
   affiche dans un tableau ce qu'il compte faire (émetteur, dossier de
   rangement, date, nouveau nom). **Rien n'est déplacé** à cette étape.
   Les documents non reconnus apparaissent surlignés (ils iront dans
   `_non_classe`, sans être renommés).
2. **« 2. Classer les fichiers ▶ »** — après une confirmation, il déplace et
   renomme réellement les fichiers, et note tout dans le journal.
3. **« ↩ Annuler le dernier classement »** — remet chaque fichier du dernier
   classement à son emplacement et son nom d'origine.

Le bouton **« Changer… »** permet de choisir un autre dossier de travail, et
**« Ouvrir le dossier »** l'ouvre dans l'explorateur de fichiers.

Voici à quoi ressemble la fenêtre après un clic sur « Analyser » :

> *(capture d'écran : le tableau liste chaque PDF avec l'émetteur détecté,
> le dossier de rangement, la date et le nouveau nom.)*

## 3. La ligne de commande (variante terminal)

D'abord, crée le dossier où tu déposeras tes PDF, puis mets-y tes documents :

```bash
mkdir -p Administration/_a_trier
# ... copie tes fichiers .pdf dans Administration/_a_trier/
```

Le reste de l'arborescence (`Prive/`, `Pro/`, `_non_classe/`) est créé
automatiquement au fur et à mesure.

### a) Simulation (recommandé pour commencer — rien n'est modifié)

```bash
python3 trier_documents.py
```

Le script affiche, pour chaque PDF, où il *serait* rangé et sous quel nom.

### b) Classement réel

Quand le résultat de la simulation te convient :

```bash
python3 trier_documents.py --execute
```

Chaque déplacement est enregistré dans `Administration/journal.csv`.

### c) Tout annuler

Pour remettre les fichiers exactement là où ils étaient :

```bash
python3 trier_documents.py --annuler
```

Le script relit `journal.csv` et replace chaque fichier à son emplacement
d'origine (sans jamais rien écraser).

---

## 4. Nom des fichiers rangés

Les documents reconnus sont renommés ainsi :

```
AAAA-MM-JJ_Emetteur_type-de-document.pdf
```

Exemple : `2026-03-12_EDF_facture-electricite.pdf`

La date provient du document lui-même (formats reconnus : `12/03/2026`,
`12 mars 2026`, `2026-03-12`). Si aucune date n'est trouvée, le script
utilise la date de modification du fichier et **le signale** à l'écran.

Un document non reconnu (confiance trop faible) part dans `_non_classe/`
**sans être renommé**, pour que tu le traites à la main.

## 5. Arborescence cible

```
Administration/
├── _a_trier/          ← tu déposes ici
├── _non_classe/       ← documents non reconnus
├── Prive/<année>/     ← Logement, Energie-Telecom, Banque-Assurance,
│                         Sante, Impots, Vehicule, Divers
└── Pro/<année>/       ← Factures-Clients, Achats-Fournisseurs, Banque,
                          Social-URSSAF, Impots-TVA, Divers
```

## 6. Personnaliser le classement

Toutes les règles sont dans **`regles.yaml`**, que tu peux modifier
librement (sans toucher au code). Pour chaque émetteur tu définis :

- `mots_cles` : les mots à chercher dans le texte du PDF,
- `domaine` : `Prive` ou `Pro`,
- `destination` : le sous-dossier de rangement,
- `emetteur` et `type` : utilisés pour construire le nom du fichier.

Une quinzaine d'exemples français (EDF, Engie, URSSAF, DGFiP, Orange, SFR,
Free, MAIF, AXA, CPAM…) sont déjà fournis : copie un bloc et adapte-le pour
ajouter les tiens.

## 7. Fichiers de test

Pour essayer l'outil sans risque, génère 3 PDF factices :

```bash
python3 generer_pdf_test.py     # crée 3 PDF dans Administration/_a_trier
python3 trier_documents.py      # simulation
python3 trier_documents.py --execute
python3 trier_documents.py --annuler
```

## 8. Contenu du projet

| Fichier                    | Rôle                                             |
|----------------------------|--------------------------------------------------|
| `trier_documents_gui.py`   | **le logiciel (fenêtre)** — à lancer pour l'interface |
| `Lancer_le_logiciel.bat`   | raccourci Windows : double-clic pour ouvrir la fenêtre |
| `trier_documents.py`       | le moteur de tri + la version ligne de commande  |
| `regles.yaml`              | les règles de classement (éditable)              |
| `generer_pdf_test.py`      | génère 3 PDF de test                             |
| `requirements.txt`         | les dépendances Python                           |
| `README.md`                | ce fichier                                       |

---

*Pour l'instant, seuls les fichiers `.pdf` sont traités.*

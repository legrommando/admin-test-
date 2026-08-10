# admin-test- — Tri automatique de documents administratifs

Petit outil en Python qui range automatiquement tes PDF administratifs.
Tu déposes tes documents en vrac dans un dossier, le script les **identifie**,
les **renomme** et les **classe** dans une arborescence Privé / Pro.

> **Sécurité d'abord :** par défaut le script est en **mode simulation**.
> Il affiche ce qu'il *ferait* mais ne touche à **aucun** fichier tant que tu
> n'ajoutes pas `--execute`. Il ne supprime et n'écrase jamais rien.

---

## 1. Installation

Il te faut Python 3 (≥ 3.8). Installe ensuite les dépendances :

```bash
pip install -r requirements.txt
```

## 2. Préparer les dossiers

Crée le dossier où tu déposeras tes PDF, puis mets-y tes documents :

```bash
mkdir -p Administration/_a_trier
# ... copie tes fichiers .pdf dans Administration/_a_trier/
```

Le reste de l'arborescence (`Prive/`, `Pro/`, `_non_classe/`) est créé
automatiquement au fur et à mesure.

## 3. Utilisation

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

| Fichier                | Rôle                                             |
|------------------------|--------------------------------------------------|
| `trier_documents.py`   | le script principal                              |
| `regles.yaml`          | les règles de classement (éditable)              |
| `generer_pdf_test.py`  | génère 3 PDF de test                             |
| `requirements.txt`     | les dépendances Python                           |
| `README.md`            | ce fichier                                       |

---

*Pour l'instant, seuls les fichiers `.pdf` sont traités.*

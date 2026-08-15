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

1. **« ① Analyser (aperçu) »** — le logiciel lit les PDF de `_a_trier` et
   affiche dans un tableau ce qu'il compte faire (émetteur, dossier de
   rangement, date, nouveau nom). **Rien n'est déplacé** à cette étape.
   Les documents non reconnus apparaissent surlignés en orange (ils iront
   dans `_non_classe`, sans être renommés).
2. **« ② Classer les fichiers »** — après une confirmation, il déplace et
   renomme réellement les fichiers, et note tout dans le journal.
3. **« ↩ Annuler le dernier classement »** — remet les fichiers **du dernier
   classement** (le dernier « lot ») à leur emplacement et nom d'origine.
   Si tu as classé plusieurs fois, seul le dernier classement est annulé.

### Les petits plus de confort

- **➕ Ajouter des PDF…** : choisis des PDF n'importe où sur ton disque, ils
  sont **copiés** dans `_a_trier` et analysés aussitôt. Tu peux aussi les
  **glisser-déposer** directement dans la fenêtre (si `tkinterdnd2` est présent).
- **✏️ Corriger un classement** : **double-clique sur une ligne** du tableau
  pour choisir toi-même la catégorie et la date — pratique quand le logiciel
  se trompe, ou pour rattraper un document `_non_classe`.
- **🔍 Documents scannés** : si l'OCR est installé (voir section 5), les PDF
  qui sont des images sont lus quand même ; ils sont repérés par une petite
  loupe 🔍 dans le tableau.
- **🌙 Thème clair / sombre** : le bouton en haut à droite. Ton choix est
  **mémorisé**, tout comme le **dernier dossier** utilisé.
- **« Changer… »** choisit un autre dossier de travail, **« Ouvrir »** l'ouvre
  dans l'explorateur de fichiers.

L'apparence moderne (style Windows 11) est fournie par le composant **sv-ttk**,
installé automatiquement par `Lancer_le_logiciel.bat`. S'il venait à manquer,
le logiciel fonctionne quand même avec l'apparence classique — rien ne bloque.

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
d'origine (sans jamais rien écraser). Ajoute **`--dernier`** pour n'annuler
que le dernier classement : `python3 trier_documents.py --annuler --dernier`.

---

## 4. Documents urgents (triés automatiquement)

Le logiciel repère les documents à **traiter en priorité** : ceux qui ont une
**date limite de paiement** (échéance) proche ou dépassée, ou qui réclament une
action (relance, mise en demeure, à payer…).

- **Ordre automatique** : dans l'aperçu, les documents s'affichent **du plus
  urgent au moins urgent**. Les urgents sont en **rouge**, avec une pastille :
  🔴 en retard · 🟠 urgent (≤ 7 jours) · 🟡 échéance proche (≤ 30 jours).
  L'échéance apparaît à côté de la date (⏰).
- **Dossier `_priorites`** : au classement, une **copie** de chaque document
  urgent est déposée dans `Administration/_priorites/`, **nommée par sa date
  d'échéance**. Le dossier se trie donc tout seul du plus urgent au moins
  urgent quand tu l'ouvres. L'original reste rangé normalement : c'est juste
  un accès rapide à ta « pile à traiter » (tu supprimes les copies au fur et à
  mesure que tu t'en occupes).

### Rappels au démarrage

À l'ouverture du logiciel (et après chaque classement), un **bandeau rouge**
te prévient s'il te reste des documents à traiter — par ex. *« ⏰ 3 documents
à traiter — dont 1 en retard »* — avec un bouton **« Ouvrir « à traiter » »**
qui t'amène directement au dossier `_priorites`. En ligne de commande :
`python trier_documents.py --rappels`.

C'est **automatique** à chaque analyse et classement — rien de plus à faire.

## 5. Lire les documents scannés (OCR) — facultatif

Beaucoup de courriers administratifs sont des **scans** : ce sont des images,
sans texte. Sans OCR, ces PDF finissent dans `_non_classe`. Pour les lire :

1. **Installer le logiciel Tesseract** (le moteur d'OCR) :
   - **Windows** : télécharge l'installateur **tesseract-ocr-w64** (paquet
     « UB Mannheim »), et pendant l'installation, coche la **langue française**.
   - **macOS** : `brew install tesseract tesseract-lang`
   - **Linux** : `sudo apt install tesseract-ocr tesseract-ocr-fra`
2. Le composant Python `pytesseract` est déjà dans `requirements.txt` (donc
   installé par `Lancer_le_logiciel.bat`).

C'est tout : au prochain lancement, le journal affichera *« OCR disponible »*
et les scans seront lus. **Si tu n'installes pas Tesseract, rien ne casse** :
seuls les scans ne sont pas reconnus.

> 💡 Le moteur **IA locale** (section ci-dessous) lit lui aussi les scans, sans
> Tesseract. Si tu utilises l'IA locale, tu n'as pas besoin de l'OCR.

## 6. IA locale (privée) — facultatif

Au lieu de reconnaître les documents par mots-clés, le logiciel peut les faire
**comprendre par une IA qui tourne sur TON ordinateur**. Rien n'est envoyé sur
Internet : tes documents restent chez toi. L'IA « à vision » lit aussi bien les
PDF texte que les **scans** (pas besoin d'OCR), et devine l'émetteur, la
catégorie, la date et le type — sans que tu aies à écrire de règles.

### Installer l'IA locale (une fois)

1. Installe **Ollama** (le logiciel qui fait tourner l'IA) depuis
   **https://ollama.com** → *Download* → version Windows.
2. Ouvre l'Invite de commandes et télécharge un modèle « à vision » :
   ```
   ollama pull llama3.2-vision
   ```
   (≈ 6 Go ; il te faut un PC avec assez de mémoire — 8 Go de RAM minimum,
   une carte graphique récente aide beaucoup.)

### Utiliser

- **Dans la fenêtre** : choisis **« IA locale (privée) »** dans la liste
  **« Méthode d'analyse »**, puis clique **Analyser** comme d'habitude.
- **En ligne de commande** : `python trier_documents.py --moteur ia`

Le journal indique si l'IA répond. **Si Ollama n'est pas lancé, le logiciel
retombe tout seul sur les mots-clés** — rien ne casse. Ton choix de méthode
est mémorisé d'une fois sur l'autre.

> ⚙️ Modèle plus léger si ton PC est modeste : `ollama pull moondream` (~1,7 Go,
> moins précis). Tu peux changer le modèle par défaut en haut de `moteur_ia.py`.

## 7. Créer un vrai `.exe` (sans installer Python) — facultatif

Pour utiliser le logiciel sur une machine **sans Python**, tu peux fabriquer
un exécutable autonome :

1. Sur une machine **où Python est installé**, double-clique sur
   **`Fabriquer_l_exe.bat`**.
2. Patiente 1–2 minutes. À la fin, tu obtiens **`dist\TriDocuments.exe`** avec
   `regles.yaml` copié à côté (tu peux l'éditer).
3. Copie ces deux éléments où tu veux, et **double-clique sur l'exe**. Le
   dossier `Administration/` sera créé à côté de l'exe.

> L'OCR (Tesseract) reste un logiciel **externe** : il n'est pas inclus dans
> l'exe. Installe-le à part (section 5) si tu veux lire les scans.

---

## 8. Recherche et doublons

Chaque document classé est enregistré dans une petite base de données locale
(`Administration/memoire.db`, via SQLite — inclus dans Python, rien à installer).
Cela apporte deux choses très pratiques.

### Retrouver un document

- **Fenêtre** : bouton **« 🔎 Rechercher… »** → tape un ou plusieurs mots
  (« EDF 2025 », « CPAM »…). Double-clic sur un résultat pour **ouvrir** le PDF.
- **Ligne de commande** : `python trier_documents.py --chercher "EDF 2025"`

### Détection des doublons

Si tu redéposes un document **déjà classé** (même contenu, même s'il a été
renommé), le logiciel le reconnaît grâce à son empreinte et l'envoie dans
**`_doublons/`** au lieu de le ranger une seconde fois. Rien n'est jamais
écrasé. Dans la fenêtre, ces documents apparaissent avec le symbole ⧉.

Tout reste **local** : la base de données ne quitte pas ton ordinateur.

## 9. Nom des fichiers rangés

Les documents reconnus sont renommés ainsi :

```
AAAA-MM-JJ_Emetteur_type-de-document.pdf
```

Exemple : `2026-03-12_EDF_facture-electricite.pdf`

La date provient du document lui-même. Formats reconnus : `2026-03-12`,
`12/03/2026` (ou `12-03-2026`), `12/03/26` (année sur 2 chiffres),
`12 mars 2026` et `12 janv. 2026` (mois abrégés). Si aucune date n'est
trouvée, le logiciel utilise la date de modification du fichier et **le
signale** (une étoile `*` apparaît à côté de la date dans le tableau).

Un document non reconnu (confiance trop faible) part dans `_non_classe/`
**sans être renommé**, pour que tu le traites à la main.

## 10. Arborescence cible

```
Administration/
├── _a_trier/          ← tu déposes ici
├── _non_classe/       ← documents non reconnus
├── _doublons/         ← documents déjà classés (détectés en double)
├── _priorites/        ← copies des documents urgents (triés par échéance)
├── journal.csv        ← historique des déplacements (pour l'annulation)
├── memoire.db         ← index des documents classés (recherche + doublons)
├── Prive/<année>/     ← Logement, Energie-Telecom, Banque-Assurance,
│                         Sante, Impots, Vehicule, Divers
└── Pro/<année>/       ← Factures-Clients, Achats-Fournisseurs, Banque,
                          Social-URSSAF, Impots-TVA, Divers
```

## 11. Personnaliser le classement

Toutes les règles sont dans **`regles.yaml`**, que tu peux modifier
librement (sans toucher au code). Pour chaque émetteur tu définis :

- `mots_cles` : les mots à chercher dans le texte du PDF,
- `domaine` : `Prive` ou `Pro`,
- `destination` : le sous-dossier de rangement,
- `emetteur` et `type` : utilisés pour construire le nom du fichier.

Une quinzaine d'exemples français (EDF, Engie, URSSAF, DGFiP, Orange, SFR,
Free, MAIF, AXA, CPAM…) sont déjà fournis : copie un bloc et adapte-le pour
ajouter les tiens. Tu peux aussi corriger un classement au cas par cas
directement dans la fenêtre (double-clic sur une ligne).

## 12. Fichiers de test et tests automatisés

Pour essayer l'outil sans risque, génère 3 PDF factices :

```bash
python3 generer_pdf_test.py     # crée 3 PDF dans Administration/_a_trier
python3 trier_documents.py      # simulation
python3 trier_documents.py --execute
python3 trier_documents.py --annuler
```

Pour vérifier que le moteur fonctionne toujours correctement (dates,
reconnaissance, collisions, annulation par lot) :

```bash
python3 -m unittest test_trier test_moteur_ia test_memoire
```

## 13. Contenu du projet

| Fichier                    | Rôle                                             |
|----------------------------|--------------------------------------------------|
| `trier_documents_gui.py`   | **le logiciel (fenêtre)** — à lancer pour l'interface |
| `Lancer_le_logiciel.bat`   | raccourci Windows : double-clic pour ouvrir la fenêtre |
| `Fabriquer_l_exe.bat`      | fabrique un `.exe` autonome (facultatif)         |
| `trier_documents.py`       | le moteur de tri (mots-clés) + la version ligne de commande |
| `moteur_ia.py`             | moteur **IA locale** (Ollama), facultatif        |
| `memoire.py`               | mémoire des documents : **recherche** + **doublons** |
| `regles.yaml`              | les règles de classement (éditable)              |
| `generer_pdf_test.py`      | génère 3 PDF de test                             |
| `test_trier.py`            | tests automatisés du moteur                      |
| `test_moteur_ia.py`        | tests du moteur IA (faux serveur Ollama)         |
| `test_memoire.py`          | tests de la mémoire (recherche, doublons)        |
| `requirements.txt`         | les dépendances Python                           |
| `README.md`                | ce fichier                                       |

---

*Pour l'instant, seuls les fichiers `.pdf` sont traités.*

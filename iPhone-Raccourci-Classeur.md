# 📱 Classer tes documents sur iPhone (app Raccourcis)

Ce guide te montre comment refaire **le même classement automatique** que le
logiciel de bureau, mais **directement sur ton iPhone 13**, sans ordinateur.

On utilise l'app **Raccourcis** (déjà installée sur iOS, icône violette 🟣).
Un « raccourci » est une petite recette d'étapes que ton téléphone exécute.
Le nôtre fait exactement ça :

1. tu **partages un PDF** (depuis Mail, Fichiers, un scan…) vers le raccourci ;
2. il **lit le texte** du PDF ;
3. il **reconnaît l'émetteur** (EDF, CPAM, Impôts…) grâce à une liste de
   mots-clés que **tu peux modifier** ;
4. il **trouve la date** dans le document ;
5. il **renomme** le fichier en `AAAA-MM-JJ_Emetteur_type.pdf` ;
6. il **range** le fichier dans `Classeur/Privé/<année>/<dossier>/`
   (ou `Classeur/Pro/…`) sur ton **iCloud Drive**.

> 💡 **Pourquoi un raccourci et pas une « appli » ?**
> Sur iPhone, Apple interdit à une application normale (ou à une page web) de
> déplacer toute seule tes fichiers dans des dossiers. **Seule l'app Raccourcis
> en a le droit.** C'est donc la bonne façon de garder le rangement automatique.

---

## ⚠️ À lire avant de commencer

- Compte **15 à 20 minutes** la première fois. Ensuite, classer un document
  prend **2 secondes**.
- Tu ne tapes quasiment pas de code : tu **ajoutes des étapes** en les
  cherchant par leur nom dans l'app.
- **Sécurité (comme sur le bureau) :** le raccourci **ne supprime jamais** et
  **n'écrase jamais** un fichier. Si un nom existe déjà, iOS ajoute
  automatiquement un numéro (` 2`, ` 3`…).
- Tes documents restent **chez toi** (sur ton iPhone / ton iCloud). Rien n'est
  envoyé sur Internet.

---

## Étape 0 — Préparer le dossier de rangement (une seule fois)

1. Ouvre l'app **Fichiers** 📁.
2. Va dans **iCloud Drive**.
3. Crée un dossier nommé **`Classeur`** (appui long dans le vide →
   *Nouveau dossier*).

C'est tout : le raccourci créera tout seul les sous-dossiers
`Privé`, `Pro`, les années et les catégories au fur et à mesure.

---

## Étape 1 — Créer le raccourci

1. Ouvre l'app **Raccourcis** 🟣.
2. En haut à droite, touche **＋** pour créer un nouveau raccourci.
3. Touche son nom en haut (« Nouveau raccourci ») et renomme-le
   **`Classer mon document`**.

Tu vas maintenant ajouter les étapes **dans l'ordre**. Pour chaque étape :
touche **« Ajouter une action »** (ou la barre de recherche en bas), **tape le
nom** de l'action indiqué en **gras**, puis touche-la pour l'ajouter.

---

## Étape 2 — Recevoir le PDF partagé

> But : pouvoir lancer le raccourci en **partageant** un PDF.

1. En haut de l'écran du raccourci, touche le petit **ⓘ** (ou la flèche de
   réglages) → active **« Afficher dans la feuille de partage »**.
2. Juste en dessous, dans **« Types reçus »**, laisse (ou choisis)
   **Fichiers PDF** et **Images** (pour les scans).

Ajoute ensuite cette action :

- **Obtenir les éléments de la feuille de partage**
  *(en anglais : « Get items from Share Sheet »)*.

> Si rien n'est partagé, on ira chercher un fichier à la main. Ajoute :
- **Si** → règle sur : *« … n'a aucune valeur »* (la cible = le résultat de
  l'action précédente).
  - À l'intérieur du **Si**, ajoute **Demander des fichiers**
    *(« Request Files »)* et coche **Autoriser plusieurs : non**.
- Touche **Fin du Si** plus tard quand tu auras compris la structure — pour
  **commencer simple**, tu peux **sauter ce bloc Si** et partager toujours un
  PDF. (Tu l'ajouteras quand tout le reste marchera.)

👉 **Version simple pour débuter :** garde seulement
**Obtenir les éléments de la feuille de partage** et avance. On améliorera après.

---

## Étape 3 — Lire le texte du PDF

Ajoute :

- **Obtenir le texte du PDF** *(« Get Text from PDF »)* — cible : le PDF reçu.

> 📸 **Document scanné (photo) ?** Si ton PDF est une image scannée, il peut ne
> pas contenir de texte. Dans ce cas, ajoute **avant** :
> **Extraire le texte de l'image** *(« Extract Text from Image »)*.
> iOS 16+ sait lire le texte d'une photo tout seul. Tu peux mettre les deux :
> d'abord essayer le texte du PDF, sinon l'image.

Ajoute ensuite, pour faciliter la reconnaissance :

- **Changer la casse** *(« Change Case »)* → **MAJUSCULES**, sur le texte obtenu.
- Range le résultat dans une variable : ajoute **Définir une variable**
  *(« Set Variable »)*, nomme-la **`Texte`**.

---

## Étape 4 — La liste des règles (le cœur du classement)

C'est **la seule partie que tu modifieras** plus tard pour ajouter tes
organismes. On met toutes les règles dans un **Dictionnaire**.

Ajoute l'action **Dictionnaire** *(« Dictionary »)*, puis touche
**Ajouter un élément** pour créer chaque ligne.

- **Clé** = un mot-clé **bien reconnaissable, en MAJUSCULES**, présent dans le
  document.
- **Valeur** = `Domaine|Dossier|Emetteur|Type` (séparé par des barres `|`).

Recopie ces lignes (ce sont les mêmes règles que `regles.yaml`) :

| Clé (mot-clé en MAJ) | Valeur (`Domaine\|Dossier\|Emetteur\|Type`)        |
|----------------------|----------------------------------------------------|
| `EDF`                | `Privé\|Energie-Telecom\|EDF\|facture-electricite` |
| `ENGIE`              | `Privé\|Energie-Telecom\|Engie\|facture-gaz`       |
| `TOTALENERGIES`      | `Privé\|Energie-Telecom\|TotalEnergies\|facture-energie` |
| `ORANGE`             | `Privé\|Energie-Telecom\|Orange\|facture-telecom`  |
| `SFR`                | `Privé\|Energie-Telecom\|SFR\|facture-telecom`     |
| `FREE`               | `Privé\|Energie-Telecom\|Free\|facture-telecom`    |
| `MAIF`               | `Privé\|Banque-Assurance\|MAIF\|assurance`         |
| `AXA`                | `Privé\|Banque-Assurance\|AXA\|assurance`          |
| `CREDIT AGRICOLE`    | `Privé\|Banque-Assurance\|CreditAgricole\|releve-compte` |
| `BNP PARIBAS`        | `Privé\|Banque-Assurance\|BNPParibas\|releve-compte` |
| `CPAM`               | `Privé\|Sante\|CPAM\|releve-remboursement`         |
| `AMELI`              | `Privé\|Sante\|CPAM\|releve-remboursement`         |
| `MUTUELLE`           | `Privé\|Sante\|Mutuelle\|releve-mutuelle`          |
| `DGFIP`              | `Privé\|Impots\|DGFiP\|avis-impot`                 |
| `IMPOT`              | `Privé\|Impots\|DGFiP\|avis-impot`                 |
| `CARTE GRISE`        | `Privé\|Vehicule\|ANTS\|carte-grise`               |
| `QUITTANCE`          | `Privé\|Logement\|Bailleur\|quittance-loyer`       |
| `URSSAF`             | `Pro\|Social-URSSAF\|URSSAF\|cotisations-sociales` |
| `TVA`                | `Pro\|Impots-TVA\|DGFiP-Pro\|declaration-tva`      |

> ➕ **Pour ajouter un organisme plus tard :** reviens dans ce Dictionnaire,
> touche **Ajouter un élément**, et mets une nouvelle ligne sur le même modèle.
> Rien d'autre à changer dans le raccourci.

Range ce dictionnaire dans une variable : **Définir une variable** →
nomme-la **`Règles`**.

---

## Étape 5 — Chercher l'émetteur dans le texte

On parcourt chaque clé des règles et on regarde si le texte la contient.

1. **Obtenir les clés du dictionnaire** *(« Get Dictionary Value »)* →
   choisis **Toutes les clés**, sur la variable **`Règles`**.
2. **Répéter pour chaque élément** *(« Repeat with Each »)* — sur ces clés.
   Dans la boucle :
   - **Si** *(« If »)* → **`Texte` contient `Élément répété`**
     *(« Repeat Item »)*.
     - À l'intérieur : **Obtenir la valeur du dictionnaire** *(« Get Dictionary
       Value »)* → la valeur pour la clé **`Élément répété`** dans **`Règles`**.
     - **Définir une variable** → nomme-la **`Trouvé`** (= cette valeur).
   - **Fin du Si**.
3. **Fin de Répéter**.

Après la boucle, gère le cas « rien trouvé » :

- **Si** → **`Trouvé` n'a aucune valeur** :
  - **Définir une variable `Trouvé`** = `Privé|Divers|Inconnu|document`.
- **Fin du Si**.

---

## Étape 6 — Séparer les 4 informations

La variable `Trouvé` ressemble à `Privé|Energie-Telecom|EDF|facture-electricite`.
On la découpe :

1. **Diviser le texte** *(« Split Text »)* → sépare **`Trouvé`** par
   **caractère personnalisé** = `|`.
2. **Obtenir un élément de la liste** *(« Get Item from List »)* →
   **Élément à l'index `1`** → **Définir une variable `Domaine`**.
3. Pareil pour l'index **`2`** → variable **`Dossier`**.
4. Index **`3`** → variable **`Emetteur`**.
5. Index **`4`** → variable **`Type`**.

---

## Étape 7 — Trouver la date

On cherche une date au format `jj/mm/aaaa` (ou `jj-mm-aaaa`, `jj.mm.aaaa`)
**ou** déjà `aaaa-mm-jj`.

1. **Faire correspondre le texte** *(« Match Text »)* sur la variable
   **`Texte`**, avec cette expression (regex) :

   ```
   \d{4}-\d{2}-\d{2}|\d{2}[/.-]\d{2}[/.-]\d{4}
   ```

2. **Obtenir un élément de la liste** → **Premier élément** des correspondances
   → **Définir une variable `DateBrute`**.
3. Gère le cas « aucune date » :
   - **Si** → **`DateBrute` n'a aucune valeur** :
     - **Date** *(« Current Date »)* → **Formater la date** *(« Format Date »)*
       → format personnalisé **`yyyy-MM-dd`** → **Définir `DateFinale`**.
   - **Sinon** :
     - On remet au format `AAAA-MM-JJ`. Le plus simple et fiable :
       **Faire correspondre le texte** sur `DateBrute` avec le groupe
       `(\d{2,4})[/.-]?(\d{2})[/.-]?(\d{2,4})`… 👉 **Pour débuter**, fais au plus
       simple : mets **`DateFinale` = `DateBrute`**. Les factures françaises
       récentes passent déjà bien ; tu peaufineras le format plus tard.
   - **Fin du Si**.

> 🧩 **Astuce fiable (optionnelle) :** si tu veux convertir proprement
> `12/03/2026` → `2026-03-12`, ajoute une action **Texte** avec
> `Analyser la date` *(« Get Dates from Input »)* sur `DateBrute`, puis
> **Formater la date** en `yyyy-MM-dd`. iOS comprend le format français tout seul.

---

## Étape 8 — Construire le nouveau nom

Ajoute une action **Texte** *(« Text »)* et écris, en insérant les variables
(touche la petite pastille de variable pour chacune) :

```
[DateFinale]_[Emetteur]_[Type]
```

→ **Définir une variable** → nomme-la **`NomFichier`**.

Exemple de résultat : `2026-03-12_EDF_facture-electricite`.

---

## Étape 9 — Ranger le fichier au bon endroit

1. On veut l'**année** pour le chemin. Ajoute **Diviser le texte** sur
   **`DateFinale`** par `-`, puis **Obtenir un élément** → **Premier élément**
   → **Définir une variable `Année`**.
2. Construis le **chemin du dossier** : action **Texte** →
   ```
   Classeur/[Domaine]/[Année]/[Dossier]
   ```
   → **Définir une variable `Chemin`**.
3. **Enregistrer le fichier** *(« Save File »)* :
   - **Service** : iCloud Drive.
   - **Destination** : désactive **« Demander où enregistrer »**.
   - **Sous-dossier / chemin** : mets la variable **`Chemin`**.
   - **Nom** : la variable **`NomFichier`** (l'extension `.pdf` est gardée
     automatiquement car on enregistre le PDF reçu).
   - **Écraser si le fichier existe** : **DÉSACTIVÉ** ← important (sécurité).

> ✅ Avec « Écraser » désactivé, iOS ajoute tout seul ` 2`, ` 3`… si un document
> du même nom existe déjà. **Aucun fichier n'est jamais perdu.**

4. (Facultatif, agréable) Ajoute **Afficher la notification**
   *(« Show Notification »)* : `Classé : [NomFichier]`.

---

## Étape 10 — Essayer !

1. Ouvre **Fichiers** ou **Mail**, trouve un PDF (facture EDF, relevé CPAM…).
2. Touche **Partager** → descends et choisis **« Classer mon document »**.
3. Va voir dans **Fichiers → iCloud Drive → Classeur** : ton document est rangé
   et renommé ! 🎉

---

## Et après ?

- **Ajouter un organisme** : Raccourcis → ton raccourci → modifie le
  **Dictionnaire `Règles`** (Étape 4). C'est le seul endroit à toucher.
- **Lancer encore plus vite** : dans les réglages du raccourci, tu peux
  l'ajouter à l'**écran d'accueil** (icône) ou le déclencher avec un
  **Automatisation** (ex. « quand j'ajoute un PDF dans le dossier Entrée »).
- **Scans / photos** : garde l'étape **Extraire le texte de l'image**
  (Étape 3) pour que même les documents photographiés soient reconnus.

---

## Rappel des correspondances (identiques au logiciel de bureau)

- **Nom de fichier** : `AAAA-MM-JJ_Emetteur_type.pdf`
- **Rangement** : `Classeur/Privé/<année>/<dossier>/` ou `Classeur/Pro/…`
- **Dossiers privés** : Logement, Energie-Telecom, Banque-Assurance, Sante,
  Impots, Vehicule, Divers.
- **Dossiers pro** : Factures-Clients, Achats-Fournisseurs, Banque,
  Social-URSSAF, Impots-TVA, Divers.

Besoin d'aide pour une étape précise ? Dis-moi laquelle bloque, je te la détaille
avec une capture d'écran de l'action exacte à chercher.

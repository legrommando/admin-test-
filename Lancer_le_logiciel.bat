@echo off
REM ============================================================================
REM  Lancer_le_logiciel.bat — Double-clique sur ce fichier pour ouvrir le
REM  logiciel de tri des documents.
REM
REM  Ce lanceur fait TOUT tout seul :
REM    1. il trouve Python (commande "py" ou "python"),
REM    2. il installe les dependances la premiere fois (si besoin),
REM    3. il ouvre la fenetre du logiciel,
REM    4. en cas d'erreur, il GARDE la fenetre ouverte pour afficher le message.
REM ============================================================================

REM On se place dans le dossier de ce fichier .bat.
cd /d "%~dp0"

REM --- 1) Trouver Python : d'abord le lanceur "py", sinon "python" ---
set "PYCMD="
py -3 --version >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD (
    python --version >nul 2>&1 && set "PYCMD=python"
)

if not defined PYCMD (
    echo.
    echo -----------------------------------------------------------------
    echo  Python n'a pas ete trouve sur cet ordinateur.
    echo  Installe-le depuis https://www.python.org/downloads/
    echo  en cochant bien la case "Add Python to PATH" pendant l'install,
    echo  puis relance ce fichier.
    echo -----------------------------------------------------------------
    echo.
    pause
    exit /b 1
)

REM --- 2) Verifier les dependances ; les installer seulement si besoin ---
%PYCMD% -c "import pdfplumber, yaml, sv_ttk" >nul 2>&1
if errorlevel 1 (
    echo Premiere utilisation : installation des composants necessaires...
    echo (cela peut prendre une minute, c'est normal)
    echo.
    %PYCMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo -----------------------------------------------------------------
        echo  L'installation des composants a echoue. Lis le message ci-dessus.
        echo -----------------------------------------------------------------
        echo.
        pause
        exit /b 1
    )
)

REM --- 3) Lancer le logiciel (la fenetre) ---
echo Demarrage du logiciel...
%PYCMD% trier_documents_gui.py

REM --- 4) Si le logiciel s'est arrete sur une erreur, on garde la fenetre ---
if errorlevel 1 (
    echo.
    echo -----------------------------------------------------------------
    echo  Le logiciel s'est arrete avec une erreur (message ci-dessus).
    echo  Copie ce message pour qu'on puisse le corriger.
    echo -----------------------------------------------------------------
    echo.
    pause
)

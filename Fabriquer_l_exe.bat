@echo off
REM ============================================================================
REM  Fabriquer_l_exe.bat — Crée un vrai .exe autonome (Windows).
REM
REM  Une fois l'exe fabrique, tu pourras lancer le logiciel d'un simple
REM  double-clic, SANS que Python soit installe sur la machine.
REM
REM  A n'utiliser qu'UNE fois (ou apres une modification du code).
REM  Necessite Python installe sur CETTE machine (pour la fabrication).
REM ============================================================================

cd /d "%~dp0"

REM --- Trouver Python ---
set "PYCMD="
py -3 --version >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD (
    python --version >nul 2>&1 && set "PYCMD=python"
)
if not defined PYCMD (
    echo Python est introuvable. Installe-le depuis https://www.python.org/downloads/
    pause
    exit /b 1
)

REM --- Installer les dependances + l'outil de fabrication (PyInstaller) ---
echo Installation des composants necessaires...
%PYCMD% -m pip install -r requirements.txt
%PYCMD% -m pip install pyinstaller

REM --- Fabriquer l'exe ---
REM  --onefile   : un seul fichier .exe
REM  --windowed  : pas de fenetre noire derriere (application graphique)
REM  --name      : nom de l'exe
REM  --collect-all : embarque bien le theme moderne et le glisser-deposer
echo.
echo Fabrication de l'exe (cela peut prendre 1 a 2 minutes)...
%PYCMD% -m PyInstaller --noconfirm --onefile --windowed ^
    --name "TriDocuments" ^
    --collect-all sv_ttk ^
    --collect-all tkinterdnd2 ^
    trier_documents_gui.py

if errorlevel 1 (
    echo.
    echo La fabrication a echoue. Lis les messages ci-dessus.
    pause
    exit /b 1
)

REM --- Placer regles.yaml A COTE de l'exe (pour qu'il soit editable) ---
copy /Y regles.yaml dist\regles.yaml >nul

echo.
echo =================================================================
echo  Termine !
echo  Ton logiciel : dossier "dist\TriDocuments.exe"
echo  Le fichier regles.yaml est copie a cote (tu peux l'editer).
echo  Copie ces deux elements ou tu veux ; double-clique sur l'exe.
echo =================================================================
echo.
pause

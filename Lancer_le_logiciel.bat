@echo off
REM ============================================================================
REM  Lancer_le_logiciel.bat — Double-clique sur ce fichier pour ouvrir le
REM  logiciel de tri des documents (la fenetre).
REM
REM  Ce petit fichier se contente de demarrer Python sur trier_documents_gui.py.
REM  Il essaie d'abord le lanceur "py" (installe avec Python sous Windows),
REM  puis "python" si le premier n'existe pas.
REM ============================================================================

REM On se place dans le dossier de ce fichier .bat (au cas ou).
cd /d "%~dp0"

REM Tentative 1 : le lanceur officiel Windows "py".
py -3 trier_documents_gui.py
if %errorlevel%==0 goto fin

REM Tentative 2 : la commande "python".
python trier_documents_gui.py
if %errorlevel%==0 goto fin

REM Si on arrive ici, Python n'a pas ete trouve ou une erreur est survenue.
echo.
echo -----------------------------------------------------------------
echo  Le logiciel n'a pas pu demarrer.
echo  Verifie que Python 3 est bien installe (https://www.python.org)
echo  et que les dependances sont installees :
echo       pip install -r requirements.txt
echo -----------------------------------------------------------------
echo.
pause

:fin

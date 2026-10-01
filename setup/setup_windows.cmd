@echo off
REM AI Engineer (Data), Labs 1 and 2: one-time setup on Windows.
REM Run it from Command Prompt, inside this folder:   setup\setup_windows.cmd
REM Safe to run again; it skips what is already done.
setlocal
cd /d "%~dp0.."
set PYTHONUTF8=1

echo.
echo [1/3] Checking Python (3.11 or newer)...
py -3 -c "import sys; assert sys.version_info >= (3, 11), sys.version; print('Python', sys.version.split()[0])"
if errorlevel 1 (
  echo Python 3.11 or newer was not found. Install it from python.org first, then run this again.
  exit /b 1
)

echo.
echo [2/3] Creating the virtual environment in .venv ...
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)
call .venv\Scripts\activate.bat

echo.
echo [3/3] Installing packages. This takes 5 to 10 minutes the first time...
python -m pip install --upgrade pip --quiet --disable-pip-version-check
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 exit /b 1
python -c "import sys; sys.path.insert(0, 'src'); import freshcart, vector_dbs; print('lab code loads; documents found:', len(list(freshcart.RAW.glob('*'))))"
if errorlevel 1 exit /b 1

echo.
echo Setup finished. Open this folder in VS Code, open notebooks\lab01_ingest.ipynb,
echo choose the .venv kernel, and run all cells.
endlocal

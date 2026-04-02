@echo off
title FrenzAI
cd /d "%~dp0"
echo.
echo  ========================================
echo   FrenzAI - Starting...
echo  ========================================
echo.

:: ============================================
:: STEP 1: Find Python 3.12
:: ============================================
set "SYSPYTHON="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "SYSPYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "SYSPYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] Python not found!
        echo  Install Python 3.12 from https://www.python.org/downloads/
        echo  Make sure to check "Add Python to PATH"
        pause
        exit /b 1
    )
    set "SYSPYTHON=python"
)

:: ============================================
:: STEP 2: Virtual Environment (inside project)
:: Packages stored in VoiceForge Studio\venv\
:: Safe from Python reinstalls + cache cleanup
:: ============================================
if not exist "venv\Scripts\python.exe" (
    echo  [SETUP] Creating virtual environment...
    echo          All packages will be stored inside this project folder.
    echo          Safe from Python reinstalls and cache cleanup.
    echo.
    "%SYSPYTHON%" -m venv venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Use venv Python for everything
set "PYTHON=%~dp0venv\Scripts\python.exe"
set "PATH=%~dp0venv\Scripts;%PATH%"

:: ============================================
:: STEP 3: Install packages (into venv)
:: ============================================
"%PYTHON%" -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo  [SETUP] Installing Python dependencies...
    echo  This only happens once and may take several minutes...
    echo.
    "%PYTHON%" -m pip install --upgrade pip >nul 2>&1
    "%PYTHON%" -m pip install -r backend\requirements.txt
    if errorlevel 1 (
        echo  [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo.
    echo  [SETUP] Installing PyTorch with GPU support...
    "%PYTHON%" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    echo.
    echo  [SETUP] Installing TTS engines...
    "%PYTHON%" -m pip install kokoro "kokoro-voices[all]" edge-tts espeakng-loader
    "%PYTHON%" -m pip install chatterbox-tts --no-deps 2>nul
    "%PYTHON%" -m pip install s3tokenizer onnx conformer diffusers --no-deps 2>nul
    "%PYTHON%" -m spacy download en_core_web_sm 2>nul
    echo.
    echo  [SETUP] All dependencies installed!
    echo.
)

:: ============================================
:: STEP 4: Check Node.js
:: ============================================
where node >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Node.js not found!
    echo  Install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo  [SETUP] Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
    echo.
)

:: ============================================
:: STEP 5: Start
:: ============================================
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:8111" ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:5173" ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo  [1/2] Starting backend server...
start /b cmd /c "cd /d "%~dp0backend" && "%~dp0venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8111 2>&1 > "%~dp0data\backend.log""

echo        Waiting for backend...
:wait_backend
timeout /t 1 /nobreak >nul
curl -s http://127.0.0.1:8111/api/health >nul 2>&1
if errorlevel 1 goto wait_backend
echo        Backend ready!
echo.

echo  [2/2] Starting frontend...
start /b cmd /c "cd /d "%~dp0frontend" && npx vite --host 127.0.0.1 --port 5173 2>&1 > "%~dp0data\frontend.log""

echo        Waiting for frontend...
timeout /t 3 /nobreak >nul
echo        Frontend ready!
echo.

echo  ========================================
echo   FrenzAI is RUNNING!
echo  ========================================
echo.
echo   Open: http://127.0.0.1:5173
echo   Packages: venv\ (safe from cleanup)
echo.
echo   Press any key to STOP the app.
echo  ========================================
echo.

start "" http://127.0.0.1:5173
pause >nul

echo.
echo  Shutting down...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:8111" ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:5173" ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo  FrenzAI stopped.
timeout /t 2 /nobreak >nul

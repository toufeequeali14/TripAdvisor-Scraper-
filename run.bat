@echo off
setlocal enabledelayedexpansion

REM ==========================================
REM TripAdvisor Scraper Runner
REM ==========================================


echo ==========================================
echo TripAdvisor Scraper
echo ==========================================

REM Create virtual environment if it doesn't exist
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing requirements...
pip install -r requirements.txt

REM Install playwright and chromium browser
echo Installing playwright and chromium browser
pip install playwright chromium

echo ==========================================
echo Login First
echo ==========================================

REM Login Tripadvisor website
python login_tripadvisor.py


echo ==========================================
echo Starting Scraper
echo ==========================================

REM Run scraper
python tripadvisor_scraper.py

echo ==========================================
echo Scraping Completed
echo ==========================================

pause
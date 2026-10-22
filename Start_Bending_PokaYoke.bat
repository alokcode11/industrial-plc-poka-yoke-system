@echo off
title Condenser Coil Bending - Poka-Yoke System
color 0A

echo ======================================================================
echo    PG ELECTROPLAST - CONDENSER COIL BENDING POKA-YOKE SYSTEM
echo ======================================================================
echo Starting Application...

cd /d "d:\Desktop\Condenser Bending"
python app_gui.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application closed with an error.
    pause
)


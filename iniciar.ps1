# Script para iniciar el servidor EPPVISION

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   EPPVISION - Sistema de Deteccion EPP" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar si estamos en el directorio correcto
if (-Not (Test-Path "backend\api\main.py")) {
    Write-Host "Error: No se encuentra el archivo main.py" -ForegroundColor Red
    Write-Host "Asegurate de ejecutar este script desde d:\VISION_EPP" -ForegroundColor Yellow
    pause
    exit
}

# Verificar si Python esta instalado
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python no esta instalado o no esta en el PATH" -ForegroundColor Red
    Write-Host "Instala Python 3.10 o superior desde https://www.python.org" -ForegroundColor Yellow
    pause
    exit
}

Write-Host ""
Write-Host "Iniciando servidor FastAPI..." -ForegroundColor Yellow
Write-Host "El sistema estara disponible en: http://localhost:8000" -ForegroundColor Green
Write-Host ""
Write-Host "Presiona Ctrl+C para detener el servidor" -ForegroundColor Yellow
Write-Host ""

# Cambiar al directorio de la API
Set-Location backend\api

# Iniciar el servidor
python main.py

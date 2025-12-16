"""
Rutas de Páginas HTML
"""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
import os

# Obtener ruta absoluta de templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

router = APIRouter()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@router.get("/dashboard")
async def dashboard(request: Request):
    """Dashboard Principal"""
    return templates.TemplateResponse("pages/dashboard.html", {"request": request})

@router.get("/monitoreo-vivo")
async def monitoreo_vivo(request: Request):
    """Monitoreo en Tiempo Real"""
    return templates.TemplateResponse("pages/monitoreo_vivo.html", {"request": request})

@router.get("/historial-alertas")
async def historial_alertas(request: Request):
    """Historial de Alertas"""
    return templates.TemplateResponse("pages/historial_alertas.html", {"request": request})

@router.get("/configuracion")
async def configuracion(request: Request):
    """Configuración del Sistema"""
    return templates.TemplateResponse("pages/configuracion.html", {"request": request})

@router.get("/procesar-videos")
async def procesar_videos(request: Request):
    """Procesar Videos Pregrabados"""
    return templates.TemplateResponse("pages/procesar_videos.html", {"request": request})

@router.get("/reportes")
async def reportes(request: Request):
    """Generar Reportes"""
    return templates.TemplateResponse("pages/reportes.html", {"request": request})

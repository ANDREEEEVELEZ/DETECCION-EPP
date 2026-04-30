"""
FastAPI - Servidor Principal
Solo renderiza las páginas HTML (maquetado)
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .routes import pages, video, images
import os


# Obtener rutas absolutas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Crear aplicación FastAPI
app = FastAPI(
    title="EPPVISION",
    description="Sistema de Detección de EPP mediante Visión Computacional",
    version="1.0.0"
)

# Montar archivos estáticos (CSS, JS, imágenes)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Incluir rutas de páginas y video
app.include_router(pages.router)
app.include_router(video.router, prefix="/api")
app.include_router(images.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Asegura que el esquema de base de datos exista antes de atender requests."""
    from backend.core.database import init_database, seed_initial_data

    init_database()
    seed_initial_data()

# Ruta raíz redirige al dashboard
@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

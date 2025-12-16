"""
Rutas de Video Streaming
"""
from fastapi import APIRouter, Response, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import cv2
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from backend.core.camera_config import camera_manager

router = APIRouter()

# Diccionario para cámaras activas
active_cameras = {}

class CameraAddRequest(BaseModel):
    physical_id: int
    nombre: str
    zona: str

class CameraUpdateRequest(BaseModel):
    nombre: str
    zona: str

def get_camera(camera_id: int):
    """Obtiene una instancia de cámara usando el ID de cámara configurada"""
    if camera_id in active_cameras and active_cameras[camera_id] is not None:
        return active_cameras[camera_id]
    
    # Obtener configuración de la cámara
    cam_config = camera_manager.get_camera_by_id(camera_id)
    if cam_config is None:
        return None
    
    physical_id = cam_config['physical_id']
    
    # Crear nueva instancia de cámara
    cap = cv2.VideoCapture(physical_id, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    if cap.isOpened():
        active_cameras[camera_id] = cap
        return cap
    return None

def generate_frames(camera_id: int):
    """Genera frames de video para streaming MJPEG"""
    camera = get_camera(camera_id)
    
    if camera is None:
        # Generar frame de error
        yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + b'\xff\xd8\xff\xe0' + b'\r\n'
        return
    
    while True:
        success, frame = camera.read()
        if not success:
            break
        
        # Convertir a JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue
        
        frame_bytes = buffer.tobytes()
        
        # Yield frame en formato multipart
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@router.get("/stream/{camera_id}")
async def video_stream(camera_id: int):
    """Endpoint de streaming de video para una cámara configurada"""
    return StreamingResponse(
        generate_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.get("/cameras/configured")
async def list_configured_cameras():
    """Lista todas las cámaras configuradas por el usuario"""
    cameras = camera_manager.get_all_cameras()
    return {"cameras": cameras}

@router.get("/cameras/physical")
async def list_physical_cameras():
    """Detecta y lista todas las cámaras físicas conectadas al sistema"""
    available = []
    
    # Detectar cámaras físicas disponibles (IDs 0-10)
    for cam_id in range(11):
        cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
        if cap.isOpened():
            # Obtener información de la cámara
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            available.append({
                "physical_id": cam_id,
                "nombre": f"Cámara #{cam_id}",
                "resolucion": f"{width}x{height}"
            })
            cap.release()
    
    return {"cameras": available}

@router.post("/cameras/add")
async def add_camera(request: CameraAddRequest):
    """Agrega una nueva cámara configurada"""
    try:
        camera = camera_manager.add_camera(
            physical_id=request.physical_id,
            nombre=request.nombre,
            zona=request.zona
        )
        return {"success": True, "camera": camera}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/cameras/{camera_id}")
async def delete_camera(camera_id: int):
    """Elimina una cámara configurada"""
    # Liberar la cámara si está activa
    if camera_id in active_cameras:
        if active_cameras[camera_id] is not None:
            active_cameras[camera_id].release()
        del active_cameras[camera_id]
    
    success = camera_manager.remove_camera(camera_id)
    if not success:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    
    return {"success": True}

@router.put("/cameras/{camera_id}")
async def update_camera(camera_id: int, request: CameraUpdateRequest):
    """Actualiza los datos de una cámara configurada"""
    camera = camera_manager.update_camera(
        camera_id=camera_id,
        nombre=request.nombre,
        zona=request.zona
    )
    
    if camera is None:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    
    return {"success": True, "camera": camera}

@router.post("/camera/release/{camera_id}")
async def release_camera(camera_id: int):
    """Libera una cámara específica"""
    if camera_id in active_cameras:
        if active_cameras[camera_id] is not None:
            active_cameras[camera_id].release()
        del active_cameras[camera_id]
        return {"message": f"Cámara {camera_id} liberada"}
    return {"message": "Cámara no estaba en uso"}

@router.on_event("shutdown")
async def shutdown_event():
    """Libera todas las cámaras al cerrar la aplicación"""
    for cam in active_cameras.values():
        if cam is not None:
            cam.release()
    active_cameras.clear()

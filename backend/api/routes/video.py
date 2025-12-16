"""
Rutas de Video Streaming
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import cv2
import asyncio

router = APIRouter()

# Diccionario para almacenar las cámaras activas
active_cameras = {}

def get_camera(camera_id: int = 0):
    """Obtiene o crea una instancia de cámara"""
    if camera_id not in active_cameras:
        active_cameras[camera_id] = cv2.VideoCapture(camera_id)
        # Configurar resolución para mejor rendimiento
        active_cameras[camera_id].set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        active_cameras[camera_id].set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    return active_cameras[camera_id]

def generate_frames(camera_id: int = 0):
    """Genera frames de video para streaming"""
    camera = get_camera(camera_id)
    
    while True:
        success, frame = camera.read()
        if not success:
            break
        
        # Codificar el frame como JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        
        # Retornar el frame en formato MJPEG
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@router.get("/stream/{camera_id}")
async def video_stream(camera_id: int):
    """
    Stream de video en tiempo real desde la cámara
    camera_id: 0 = Cámara predeterminada de la PC
    """
    return StreamingResponse(
        generate_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.get("/camera/status/{camera_id}")
async def camera_status(camera_id: int):
    """Verifica el estado de una cámara"""
    try:
        camera = get_camera(camera_id)
        is_opened = camera.isOpened()
        
        if is_opened:
            # Probar captura
            success, _ = camera.read()
            return {
                "camera_id": camera_id,
                "status": "online" if success else "error",
                "message": "Cámara funcionando" if success else "Error al leer frames"
            }
        else:
            return {
                "camera_id": camera_id,
                "status": "offline",
                "message": "Cámara no disponible"
            }
    except Exception as e:
        return {
            "camera_id": camera_id,
            "status": "error",
            "message": str(e)
        }

@router.post("/camera/release/{camera_id}")
async def release_camera(camera_id: int):
    """Libera una cámara específica"""
    if camera_id in active_cameras:
        active_cameras[camera_id].release()
        del active_cameras[camera_id]
        return {"message": f"Cámara {camera_id} liberada"}
    return {"message": "Cámara no estaba activa"}

@router.on_event("shutdown")
async def shutdown_cameras():
    """Libera todas las cámaras al cerrar la aplicación"""
    for camera in active_cameras.values():
        camera.release()
    active_cameras.clear()

"""
Rutas de Video Streaming
"""
from fastapi import APIRouter, Response, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import cv2
import time
import sys
import os
import uuid
import shutil
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from backend.core.camera_config import camera_manager

router = APIRouter()

# Diccionario para cámaras activas
active_cameras = {}

# Diccionario para videos en procesamiento
active_videos = {}

# Directorio temporal para videos
TEMP_VIDEO_DIR = Path("backend/temp_videos")
TEMP_VIDEO_DIR.mkdir(exist_ok=True)

# Detector EPP global (se carga bajo demanda)
epp_detector = None

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
    
    print(f"[VIDEO] Intentando abrir cámara física ID={physical_id} (Camera DB ID={camera_id})")
    
    # Crear nueva instancia de cámara
    cap = cv2.VideoCapture(physical_id, cv2.CAP_DSHOW)
    
    if not cap.isOpened():
        print(f"[VIDEO ERROR] No se pudo abrir cámara física ID={physical_id}. Puede estar en uso por otra aplicación.")
        return None
    
    # Configurar resolución
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    print(f"[VIDEO OK] Cámara física ID={physical_id} abierta correctamente")
    active_cameras[camera_id] = cap
    return cap

def generate_frames(camera_id: int, enable_detection: bool = False):
    """Genera frames de video para streaming MJPEG"""
    global epp_detector
    
    camera = get_camera(camera_id)
    
    if camera is None:
        print(f"[VIDEO ERROR] No se pudo obtener cámara para streaming (camera_id={camera_id})")
        # Generar frame de error
        yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + b'\xff\xd8\xff\xe0' + b'\r\n'
        return
    
    # Cargar detector si está habilitada la detección
    if enable_detection and epp_detector is None:
        try:
            print("[INFO] Cargando modelo EPP por primera vez...")
            # Import relativo desde la estructura del proyecto
            import sys
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            sys.path.insert(0, project_root)
            
            from backend.core.epp_detector import EPPDetector
            epp_detector = EPPDetector(model_path="models/best.pt")
            print("[INFO] Modelo EPP cargado exitosamente")
        except Exception as e:
            print(f"[ERROR] No se pudo cargar modelo EPP: {e}")
            import traceback
            traceback.print_exc()
            enable_detection = False
    
    print(f"[VIDEO] Iniciando streaming para camera_id={camera_id} (detección={'ON' if enable_detection else 'OFF'})")
    
    # Contador de frames para no guardar cada frame (solo cada 30 frames = ~1 seg)
    frame_count = 0
    last_alert_time = 0
    
    while True:
        success, frame = camera.read()
        if not success:
            print(f"[VIDEO ERROR] No se pudo leer frame de camera_id={camera_id}")
            break
        
        # Procesar con detector EPP si está habilitado
        if enable_detection and epp_detector is not None:
            try:
                frame, detections, compliance = epp_detector.process_frame(frame, draw=True)
                
                # Guardar detección y generar alerta solo cada 30 frames y si hay incumplimiento
                frame_count += 1
                current_time = time.time()
                
                if frame_count % 30 == 0 and compliance['estado'] != 'C':
                    # Evitar spam de alertas (mínimo 5 segundos entre alertas de la misma cámara)
                    if current_time - last_alert_time > 5:
                        try:
                            from backend.core.alert_manager import alert_manager
                            
                            # Guardar detección en BD con snapshot
                            deteccion_id = alert_manager.save_detection(camera_id, detections, compliance, frame=frame)
                            
                            # Generar alerta
                            if deteccion_id:
                                alert_manager.generate_alert(camera_id, deteccion_id, compliance)
                                last_alert_time = current_time
                        except Exception as e:
                            print(f"[ERROR] Error guardando detección/alerta: {e}")
                
            except Exception as e:
                print(f"[ERROR] Error en detección EPP: {e}")
        
        # Convertir a JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue
        
        frame_bytes = buffer.tobytes()
        
        # Yield frame en formato multipart
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@router.get("/stream/{camera_id}")
async def video_stream(camera_id: int, detect: bool = False):
    """Endpoint de streaming de video para una cámara configurada"""
    return StreamingResponse(
        generate_frames(camera_id, enable_detection=detect),
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
    
    # Obtener nombres reales de cámaras en Windows usando DirectShow
    try:
        import pygrabber.dshow_graph as dsg
        device_names = dsg.FilterGraph().get_input_devices()
    except:
        device_names = []
    
    # Detectar cámaras físicas disponibles (IDs 0-10)
    for cam_id in range(11):
        cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
        if cap.isOpened():
            # Obtener información de la cámara
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Usar nombre real si está disponible, sino usar nombre genérico
            nombre = device_names[cam_id] if cam_id < len(device_names) else f"Cámara #{cam_id}"
            
            available.append({
                "physical_id": cam_id,
                "nombre": nombre,
                "resolucion": f"{width}x{height}"
            })
            cap.release()
    
    return {"cameras": available}

@router.post("/cameras/add")
async def add_camera(request: CameraAddRequest):
    """Agrega una nueva cámara configurada"""
    try:
        print(f"[DEBUG] Intentando agregar cámara: physical_id={request.physical_id}, nombre={request.nombre}, zona={request.zona}")
        camera = camera_manager.add_camera(
            physical_id=request.physical_id,
            nombre=request.nombre,
            zona=request.zona
        )
        print(f"[DEBUG] Cámara agregada exitosamente: {camera}")
        return {"success": True, "camera": camera}
    except ValueError as e:
        print(f"[ERROR] ValueError: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

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

@router.get("/alerts/recent")
async def get_recent_alerts(limit: int = 10):
    """Obtiene las alertas más recientes"""
    from backend.core.alert_manager import alert_manager
    alertas = alert_manager.get_recent_alerts(limit=limit)
    return {"success": True, "alerts": alertas}

@router.get("/alerts/count")
async def get_alerts_count(estado: str = "pendiente"):
    """Obtiene el conteo de alertas por estado"""
    from backend.core.alert_manager import alert_manager
    count = alert_manager.get_alerts_count(estado=estado)
    return {"success": True, "count": count}

@router.get("/alerts/history")
async def get_alerts_history(limit: int = 50, tipo: str = None, camera_id: int = None):
    """Obtiene historial completo de alertas con filtros"""
    from backend.core.alert_manager import alert_manager
    db = alert_manager._get_db()
    try:
        from backend.core.database import Alerta
        
        query = db.query(Alerta).order_by(Alerta.timestamp.desc())
        
        # Aplicar filtros
        if tipo and tipo != 'todas':
            query = query.filter(Alerta.tipo.contains(tipo))
        
        if camera_id:
            query = query.filter(Alerta.camera_id == camera_id)
        
        alertas = query.limit(limit).all()
        
        result = []
        for alerta in alertas:
            result.append({
                'id': alerta.id,
                'camera_id': alerta.camera_id,
                'camera_nombre': alerta.camera.nombre if alerta.camera else 'Desconocida',
                'zona': alerta.camera.zona if alerta.camera else '',
                'timestamp': alerta.timestamp.strftime('%H:%M %p') if alerta.timestamp else '',
                'fecha': alerta.timestamp.strftime('%d/%m/%Y') if alerta.timestamp else '',
                'tipo': alerta.tipo,
                'severidad': alerta.severidad,
                'mensaje': alerta.mensaje,
                'estado': alerta.estado,
                'imagen_path': alerta.deteccion.imagen_path if alerta.deteccion and alerta.deteccion.imagen_path else None
            })
        
        return {"success": True, "alerts": result}
    except Exception as e:
        print(f"[ERROR] Error en historial: {e}")
        return {"success": False, "alerts": [], "error": str(e)}
    finally:
        db.close()


# ==================== PROCESAMIENTO DE VIDEOS ====================

@router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...)):
    """Recibe un video para procesamiento temporal"""
    try:
        # Validar extensión
        allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv']
        file_extension = Path(file.filename).suffix.lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Formato no soportado. Use: {', '.join(allowed_extensions)}")
        
        # Generar ID único para el video
        video_id = str(uuid.uuid4())
        video_path = TEMP_VIDEO_DIR / f"{video_id}{file_extension}"
        
        # Guardar archivo temporalmente
        with video_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Obtener información del video
        cap = cv2.VideoCapture(str(video_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        # Almacenar en diccionario de videos activos
        active_videos[video_id] = {
            'path': str(video_path),
            'filename': file.filename,
            'total_frames': total_frames,
            'fps': fps,
            'duration': duration,
            'width': width,
            'height': height,
            'stats': {
                'frames_procesados': 0,
                'detecciones_totales': 0,
                'personas_detectadas': 0,
                'epp_incorrecto': 0
            }
        }
        
        print(f"[VIDEO UPLOAD] {file.filename} guardado como {video_id} ({duration:.1f}s, {total_frames} frames)")
        
        return {
            "success": True,
            "video_id": video_id,
            "filename": file.filename,
            "duration": round(duration, 2),
            "total_frames": total_frames,
            "fps": round(fps, 2),
            "resolution": f"{width}x{height}"
        }
        
    except Exception as e:
        print(f"[ERROR] Upload video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/stream/{video_id}")
async def stream_video_with_detection(video_id: str):
    """Stream de video con detección EPP en tiempo real"""
    
    if video_id not in active_videos:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    
    def generate_video_frames():
        global epp_detector
        
        video_info = active_videos.get(video_id)
        if not video_info:
            print(f"[ERROR] Video {video_id} no encontrado en active_videos")
            return
            
        video_path = video_info['path']
        print(f"[VIDEO] Iniciando stream para: {video_info['filename']}")
        
        # Cargar detector si no existe
        if epp_detector is None:
            try:
                print("[INFO] Cargando modelo EPP para procesamiento de video...")
                import sys
                import os
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                sys.path.insert(0, project_root)
                from backend.core.epp_detector import EPPDetector
                epp_detector = EPPDetector()
                print("[INFO] Modelo EPP cargado exitosamente para video")
            except Exception as e:
                print(f"[ERROR] Error cargando modelo EPP: {e}")
                import traceback
                traceback.print_exc()
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"[ERROR] No se pudo abrir video: {video_path}")
            return
            
        frame_count = 0
        
        try:
            while True:
                ret, frame = cap.read()
                
                if not ret:
                    # Video terminado
                    print(f"[VIDEO] Procesamiento completado: {video_info['filename']}")
                    break
                
                frame_count += 1
                
                try:
                    # Procesar con detector EPP si está disponible
                    if epp_detector is not None:
                        frame, detections, compliance = epp_detector.process_frame(frame, draw=True)
                        
                        # Actualizar estadísticas
                        video_info['stats']['frames_procesados'] = frame_count
                        if detections:
                            video_info['stats']['detecciones_totales'] += len(detections)
                            video_info['stats']['personas_detectadas'] = len(detections)
                            if compliance['estado'] != 'C':
                                video_info['stats']['epp_incorrecto'] += 1
                        else:
                            video_info['stats']['personas_detectadas'] = 0
                        
                        # Info de progreso en el frame
                        progress = (frame_count / video_info['total_frames']) * 100 if video_info['total_frames'] > 0 else 0
                        cv2.putText(frame, f"Progreso: {progress:.1f}% | Frame: {frame_count}/{video_info['total_frames']}", 
                                  (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                        
                        # Contador de personas detectadas
                        cv2.putText(frame, f"Personas: {len(detections)} | EPP Incorrecto: {video_info['stats']['epp_incorrecto']}", 
                                  (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    else:
                        # Si no hay detector, solo actualizar contador
                        video_info['stats']['frames_procesados'] = frame_count
                        cv2.putText(frame, "Cargando modelo EPP...", 
                                  (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    
                except Exception as e:
                    print(f"[ERROR] Error procesando frame {frame_count}: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Codificar frame
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                
                if not ret:
                    print(f"[ERROR] No se pudo codificar frame {frame_count}")
                    continue
                
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
                # Control de FPS (aproximado para procesamiento)
                time.sleep(1/30)  # ~30 FPS
                
        except Exception as e:
            print(f"[ERROR] Error en stream de video: {e}")
            import traceback
            traceback.print_exc()
        finally:
            cap.release()
            print(f"[VIDEO] Stream finalizado para {video_id}")
    
    return StreamingResponse(
        generate_video_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/videos/stats/{video_id}")
async def get_video_stats(video_id: str):
    """Obtiene estadísticas del video en procesamiento"""
    
    if video_id not in active_videos:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    
    video_info = active_videos[video_id]
    stats = video_info['stats']
    
    progress = (stats['frames_procesados'] / video_info['total_frames']) * 100 if video_info['total_frames'] > 0 else 0
    
    return {
        "success": True,
        "video_id": video_id,
        "filename": video_info['filename'],
        "progress": round(progress, 2),
        "frames_procesados": stats['frames_procesados'],
        "total_frames": video_info['total_frames'],
        "detecciones_totales": stats['detecciones_totales'],
        "personas_detectadas": stats['personas_detectadas'],
        "epp_incorrecto": stats['epp_incorrecto'],
        "duracion": video_info['duration'],
        "fps": video_info['fps']
    }


@router.delete("/videos/{video_id}")
async def delete_video(video_id: str):
    """Elimina un video temporal"""
    
    if video_id not in active_videos:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    
    try:
        video_path = Path(active_videos[video_id]['path'])
        
        # Eliminar archivo
        if video_path.exists():
            video_path.unlink()
            print(f"[VIDEO] Archivo eliminado: {video_path}")
        
        # Remover del diccionario
        del active_videos[video_id]
        
        return {"success": True, "message": "Video eliminado"}
        
    except Exception as e:
        print(f"[ERROR] Error eliminando video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

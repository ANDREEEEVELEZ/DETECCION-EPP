"""
Rutas de Video Streaming
"""
from fastapi import APIRouter, Response, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import io
import csv
import json
import zipfile
import cv2
import time
import sys
import os
import uuid
import shutil
import re
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


def _open_camera_capture(physical_id: int):
    """Intenta abrir una cámara con distintos backends para mayor compatibilidad."""
    attempts = [
        ("DSHOW", cv2.CAP_DSHOW),
        ("AUTO", None),
    ]

    for backend_name, backend in attempts:
        cap = cv2.VideoCapture(physical_id, backend) if backend is not None else cv2.VideoCapture(physical_id)
        if cap.isOpened():
            print(f"[VIDEO] Cámara física ID={physical_id} abierta con backend {backend_name}")
            return cap
        cap.release()

    return None

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
    
    # Crear nueva instancia de cámara con fallback de backend
    cap = _open_camera_capture(physical_id)
    
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
            print("=" * 60)
            print("[INFO] Cargando modelo EPP por primera vez...")
            # Import relativo desde la estructura del proyecto
            import sys
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            sys.path.insert(0, project_root)
            
            from backend.core.epp_detector import EPPDetector
            model_path = os.getenv("EPP_MODEL_PATH", "models/best 22042026V1.pt")
            conf_threshold = float(os.getenv("EPP_CONF_THRESHOLD", "0.20"))
            epp_detector = EPPDetector(model_path=model_path, conf_threshold=conf_threshold)
            print("[INFO] Modelo EPP cargado exitosamente")
            print(f"[INFO] Modelo de detección: {model_path}")
            print(f"[INFO] Umbral de confianza: {conf_threshold}")
            if getattr(epp_detector, 'model_missing_epp', None):
                print(f"[WARNING] El modelo no soporta estos EPP: {epp_detector.model_missing_epp}")
            print(f"[INFO] Modelo de pose disponible: {epp_detector.pose_model is not None}")
            print("=" * 60)
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
                # DEBUG: Mostrar info de detección cada 60 frames
                if frame_count % 60 == 0:
                    print(f"[DEBUG] Frame {frame_count}: Modelo pose disponible: {epp_detector.pose_model is not None}")
                
                frame, detections, compliance = epp_detector.process_frame(frame, draw=True)
                
                # DEBUG: Mostrar detecciones con posicionamiento cada 60 frames
                if frame_count % 60 == 0 and len(detections) > 0:
                    print(f"[DEBUG] Detecciones: {len(detections)}")
                    for det in detections:
                        print(f"  - {det['epp_type']}: has_epp={det['has_epp']}, correctly_positioned={det.get('correctly_positioned', 'N/A')}")
                
                # Guardar detección y generar alerta solo cada 30 frames y si hay incumplimiento
                frame_count += 1
                current_time = time.time()
                
                if frame_count % 30 == 0 and compliance['estado'] != 'C':
                    # Evitar spam de alertas (mínimo 5 segundos entre alertas de la misma cámara)
                    if current_time - last_alert_time > 5:
                        try:
                            from backend.core.alert_manager import alert_manager
                            
                            # Guardar detección en BD con snapshot
                            if compliance.get('estado') in ('I', 'N'):
                                deteccion_id = alert_manager.save_detection(camera_id, detections, compliance, frame=frame)
                            else:
                                deteccion_id = None
                            
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
        cap = _open_camera_capture(cam_id)
        if cap is None:
            continue

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


@router.get("/alerts/{alert_id}/detail")
async def get_alert_detail(alert_id: int):
    """Obtiene el detalle de una alerta, incluyendo evidencia y desglose de EPP."""
    from backend.core.alert_manager import alert_manager
    from backend.core.database import Alerta, DeteccionEPP, TipoEPP

    db = alert_manager._get_db()
    try:
        alerta = db.query(Alerta).filter(Alerta.id == alert_id).first()
        if not alerta:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")

        deteccion = alerta.deteccion
        if deteccion is None:
            return {
                "success": True,
                "alerta": {
                    "id": alerta.id,
                    "mensaje": alerta.mensaje,
                    "severidad": alerta.severidad,
                    "estado": alerta.estado,
                    "timestamp": alerta.timestamp.strftime('%d/%m/%Y %H:%M %p') if alerta.timestamp else '',
                },
                "deteccion": None,
                "epp": {
                    "correctos": [],
                    "incorrectos": [],
                    "no_usa": [],
                    "no_evaluable_modelo": [],
                    "detalle": []
                }
            }

        observaciones = deteccion.observaciones or ""
        match_no_evaluable = re.search(r"No evaluable por modelo:\s*(.+)$", observaciones)
        no_evaluable_modelo = []
        if match_no_evaluable:
            no_evaluable_modelo = [item.strip() for item in match_no_evaluable.group(1).split(',') if item.strip()]

        detalle_epp = []
        correctos = []
        incorrectos = []
        no_usa = []

        registros_epp = (
            db.query(DeteccionEPP, TipoEPP)
            .join(TipoEPP, DeteccionEPP.tipo_epp_id == TipoEPP.id)
            .filter(DeteccionEPP.deteccion_id == deteccion.id)
            .all()
        )

        for deteccion_epp, tipo_epp in registros_epp:
            nombre = tipo_epp.nombre.lower()
            detectado = bool(deteccion_epp.detectado)
            uso_correcto = deteccion_epp.uso_correcto

            if detectado and uso_correcto == 1:
                estado = "correcto"
                correctos.append(nombre)
            elif detectado:
                estado = "incorrecto"
                incorrectos.append(nombre)
            elif nombre in no_evaluable_modelo:
                estado = "no_evaluable_modelo"
            else:
                estado = "no_usa"
                no_usa.append(nombre)

            detalle_epp.append({
                "tipo": tipo_epp.nombre,
                "estado": estado,
                "detectado": detectado,
                "uso_correcto": None if deteccion_epp.uso_correcto is None else bool(deteccion_epp.uso_correcto),
                "confianza": deteccion_epp.confianza,
                "bbox": {
                    "x": deteccion_epp.bbox_x,
                    "y": deteccion_epp.bbox_y,
                    "width": deteccion_epp.bbox_width,
                    "height": deteccion_epp.bbox_height,
                }
            })

        return {
            "success": True,
            "alerta": {
                "id": alerta.id,
                "mensaje": alerta.mensaje,
                "tipo": alerta.tipo,
                "severidad": alerta.severidad,
                "estado": alerta.estado,
                "timestamp": alerta.timestamp.strftime('%d/%m/%Y %H:%M %p') if alerta.timestamp else '',
                "camera_nombre": alerta.camera.nombre if alerta.camera else 'Desconocida',
                "zona": alerta.camera.zona if alerta.camera else '',
            },
            "deteccion": {
                "id": deteccion.id,
                "estado_epp": deteccion.estado_epp,
                "observaciones": observaciones,
                "imagen_path": deteccion.imagen_path,
                "timestamp": deteccion.timestamp.strftime('%d/%m/%Y %H:%M %p') if deteccion.timestamp else '',
            },
            "epp": {
                "correctos": correctos,
                "incorrectos": incorrectos,
                "no_usa": no_usa,
                "no_evaluable_modelo": no_evaluable_modelo,
                "detalle": detalle_epp,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Error obteniendo detalle de alerta {alert_id}: {e}")
        return {"success": False, "error": str(e)}
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
            'paused': False,
            'current_frame_number': 0,
            'last_frame_bytes': None,
            'last_frame_original': None,  # Frame original sin anotaciones para reprocesar si es necesario
            'last_observation': None,
            'pause_sequence': 0,
            'observation_points': [],
            'stats': {
                'frames_procesados': 0,
                'detecciones_totales': 0,
                'personas_unicas': set(),  # Guardar IDs de personas para contar únicas
                'frames_con_incumplimiento': 0,  # Frames donde hay incumplimiento
                'frames_conformes': 0,  # Frames donde todo está bien
                'desglose_epp': {
                    'casco': 0,
                    'chaleco': 0,
                    'guantes': 0,
                    'botas': 0,
                    'gafas': 0
                }
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
                if video_info.get('paused'):
                    paused_frame = video_info.get('last_frame_bytes')
                    if paused_frame:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + paused_frame + b'\r\n')
                    time.sleep(0.2)
                    continue

                ret, frame = cap.read()
                
                if not ret:
                    # Video terminado
                    print(f"[VIDEO] Procesamiento completado: {video_info['filename']}")
                    break
                
                frame_count += 1
                
                # Guardar frame original antes de procesarlo
                frame_original = frame.copy()
                
                try:
                    # Procesar con detector EPP si está disponible
                    if epp_detector is not None:
                        frame, detections, compliance = epp_detector.process_frame(frame, draw=True)
                        
                        # Actualizar estadísticas
                        video_info['stats']['frames_procesados'] = frame_count
                        if detections:
                            video_info['stats']['detecciones_totales'] += len(detections)
                            
                            # Contar personas únicas (aproximado: por bbox de EPP detectado)
                            for det in detections:
                                if det['epp_type'] in video_info['stats']['desglose_epp']:
                                    video_info['stats']['desglose_epp'][det['epp_type']] += 1
                            
                            # Contar frames con incumplimiento (no acumular por frame, solo contar una vez)
                            if compliance['estado'] == 'C':
                                video_info['stats']['frames_conformes'] += 1
                            elif compliance['estado'] in ('I', 'N'):
                                video_info['stats']['frames_con_incumplimiento'] += 1
                        else:
                            # Frame sin detecciones, pero si es conforme contar
                            if compliance['estado'] == 'C':
                                video_info['stats']['frames_conformes'] += 1
                        
                        # Info de progreso en el frame
                        progress = (frame_count / video_info['total_frames']) * 100 if video_info['total_frames'] > 0 else 0
                        cv2.putText(frame, f"Progreso: {progress:.1f}% | Frame: {frame_count}/{video_info['total_frames']}", 
                                  (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                        
                        # Contador de personas detectadas
                        cv2.putText(frame, f"Personas: {len(detections)} | EPP Incorrecto: {video_info['stats']['epp_incorrecto']}", 
                                  (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                        video_info['current_frame_number'] = frame_count
                        video_info['last_observation'] = {
                            'frame_number': frame_count,
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'estado': compliance.get('estado'),
                            'score': compliance.get('score', 0),
                            'mensaje': compliance.get('mensaje', ''),
                            'epp_status': compliance.get('epp_status', {}),
                            'epp_positioning': compliance.get('epp_positioning', {}),
                            'detections': [
                                {
                                    'class': det.get('class'),
                                    'epp_type': det.get('epp_type'),
                                    'has_epp': det.get('has_epp'),
                                    'correctly_positioned': det.get('correctly_positioned', False),
                                    'confidence': det.get('confidence', 0),
                                }
                                for det in detections
                            ]
                        }
                    else:
                        # Si no hay detector, solo actualizar contador
                        video_info['stats']['frames_procesados'] = frame_count
                        cv2.putText(frame, "Cargando modelo EPP...", 
                                  (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    
                except Exception as e:
                    print(f"[ERROR] Error procesando frame {frame_count}: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Codificar frame anotado para mostrar en stream
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                
                if not ret:
                    print(f"[ERROR] No se pudo codificar frame {frame_count}")
                    continue
                
                frame_bytes = buffer.tobytes()
                video_info['last_frame_bytes'] = frame_bytes
                video_info['last_frame_original'] = frame_original.copy()  # Guardar original para reprocesar si es necesario
                
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
    
    # Calcular métrica de incumplimiento por tipo de EPP
    epp_incorrecto_detalle = stats.get('desglose_epp', {})
    
    return {
        "success": True,
        "video_id": video_id,
        "filename": video_info['filename'],
        "progress": round(progress, 2),
        "frames_procesados": stats['frames_procesados'],
        "total_frames": video_info['total_frames'],
        "frames_con_incumplimiento": stats['frames_con_incumplimiento'],
        "frames_conformes": stats['frames_conformes'],
        "detecciones_totales": stats['detecciones_totales'],
        "desglose_epp": epp_incorrecto_detalle,
        "duracion": video_info['duration'],
        "fps": video_info['fps']
    }


@router.post("/videos/{video_id}/pause")
async def pause_video(video_id: str):
    """Pausa el procesamiento del video y congela el frame actual."""
    global epp_detector
    
    if video_id not in active_videos:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    video_info = active_videos[video_id]
    video_info['paused'] = True

    # Obtener la observación del frame actual que el stream procesó
    observation = video_info.get('last_observation')
    frame_original = video_info.get('last_frame_original')
    
    # Si no hay observación, intentar procesar el frame original ahora
    if (not observation or not observation.get('epp_positioning')) and frame_original is not None and epp_detector is not None:
        try:
            print(f"[PAUSE] Reprocesando frame original para obtener datos...")
            frame_processed, detections, compliance = epp_detector.process_frame(frame_original.copy(), draw=False)
            
            observation = {
                'frame_number': video_info.get('current_frame_number', 0),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'estado': compliance.get('estado', 'N/A'),
                'score': compliance.get('score', 0),
                'mensaje': compliance.get('mensaje', ''),
                'epp_status': compliance.get('epp_status', {}),
                'epp_positioning': compliance.get('epp_positioning', {}),
                'detections': [
                    {
                        'class': det.get('class'),
                        'epp_type': det.get('epp_type'),
                        'confidence': det.get('confidence', 0),
                    }
                    for det in detections
                ]
            }
            print(f"[PAUSE] ✓ Frame reprocesado - Estado: {observation.get('estado')}, EPP: {observation.get('epp_positioning')}")
        except Exception as e:
            print(f"[ERROR] Error reprocesando frame al pausar: {e}")
            import traceback
            traceback.print_exc()
    
    # Si aún no hay observación, crear una mínima
    if not observation:
        observation = {
            'frame_number': video_info.get('current_frame_number', 0),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'estado': 'N/A',
            'score': 0,
            'mensaje': 'Sin datos de análisis disponibles',
            'epp_status': {},
            'epp_positioning': {}
        }
    
    frame_number = observation.get('frame_number', 0)
    video_info['pause_sequence'] = video_info.get('pause_sequence', 0) + 1
    capture_index = video_info['pause_sequence']
    
    snapshot_bytes = video_info.get('last_frame_bytes')
    if snapshot_bytes is None and video_info.get('last_frame_original') is not None:
        try:
            ok, buffer = cv2.imencode('.jpg', video_info['last_frame_original'], [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                snapshot_bytes = buffer.tobytes()
        except Exception:
            snapshot_bytes = None

    observation_record = {
        **observation,
        'capture_index': capture_index,
        'snapshot_bytes': snapshot_bytes
    }
    video_info['observation_points'].append(observation_record)
    print(f"[PAUSE] ✓ Observación guardada - Captura: {capture_index}, Frame: {frame_number}, Estado: {observation.get('estado')}")

    return {
        'success': True,
        'paused': True,
        'frame_number': frame_number,
        'observation': observation,
        'observations_count': len(video_info['observation_points']),
        'capture_index': capture_index
    }


@router.post("/videos/{video_id}/resume")
async def resume_video(video_id: str):
    """Reanuda el procesamiento del video."""
    if video_id not in active_videos:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    active_videos[video_id]['paused'] = False
    return {'success': True, 'paused': False}


@router.get("/videos/{video_id}/observations/export")
async def export_observations(video_id: str):
    """Exporta una ficha automática con tabla agregada y snapshots de los momentos observados."""
    if video_id not in active_videos:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    video_info = active_videos[video_id]
    observations = video_info.get('observation_points', [])
    if not observations:
        raise HTTPException(status_code=404, detail="No hay observaciones para exportar")

    epps = ['casco', 'chaleco', 'guantes', 'botas', 'gafas']
    summary = {
        epp: {'C': 0, 'I': 0, 'N': 0, 'total': 0}
        for epp in epps
    }

    rows = []
    for obs in observations:
        posicionamiento = obs.get('epp_positioning', {}) or {}
        detections = obs.get('detections', [])
        fila = {'frame_number': obs.get('frame_number'), 'timestamp': obs.get('timestamp'), 'estado': obs.get('estado'), 'mensaje': obs.get('mensaje')}
        
        # Contar detecciones individuales por tipo de EPP
        epp_detection_count = {epp: {'C': 0, 'I': 0, 'N': 0} for epp in epps}
        
        # Agrupar detecciones por epp_type
        detections_by_type = {epp: [] for epp in epps}
        for det in detections:
            epp_type = det.get('epp_type', '').lower()
            if epp_type in detections_by_type:
                detections_by_type[epp_type].append(det)
        
        # Contar detecciones, usando epp_positioning para determinar estado
        for epp in epps:
            det_list = detections_by_type[epp]
            state = posicionamiento.get(epp, 'ausente')
            
            if det_list:
                # Hay detecciones de este EPP
                count = len(det_list)
                if state == 'correcto':
                    epp_detection_count[epp]['C'] = count
                elif state == 'incorrecto':
                    epp_detection_count[epp]['I'] = count
                else:  # 'ausente'
                    epp_detection_count[epp]['N'] = count
            else:
                # No hay detecciones de este EPP
                if state == 'ausente' or state == '' or state is None:
                    epp_detection_count[epp]['N'] = 1
        
        # Agregar conteos a la fila y al resumen
        for epp in epps:
            c = epp_detection_count[epp]['C']
            i = epp_detection_count[epp]['I']
            n = epp_detection_count[epp]['N']
            total = c + i + n
            
            # Determinar código predominante para la fila
            if c > 0:
                code = 'C'
            elif i > 0:
                code = 'I'
            elif n > 0:
                code = 'N'
            else:
                code = 'N'
            
            fila[epp] = code
            
            # Agregar al resumen
            summary[epp]['C'] += c
            summary[epp]['I'] += i
            summary[epp]['N'] += n
        
        rows.append(fila)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['frame_number', 'timestamp', 'estado_general', 'mensaje', 'casco', 'chaleco', 'guantes', 'botas', 'gafas'])
    for row in rows:
        writer.writerow([row['frame_number'], row['timestamp'], row['estado'], row['mensaje'], row['casco'], row['chaleco'], row['guantes'], row['botas'], row['gafas']])

    writer.writerow([])
    writer.writerow(['resumen_detecciones_individuales'])
    writer.writerow(['epp', 'Correcto(C)', 'Incorrecto(I)', 'No uso(N)', 'Total', '%C', '%I', '%N'])
    for epp in epps:
        c = summary[epp]['C']
        i = summary[epp]['I']
        n = summary[epp]['N']
        total = c + i + n
        pct_c = (c / total * 100) if total else 0
        pct_i = (i / total * 100) if total else 0
        pct_n = (n / total * 100) if total else 0
        writer.writerow([
            epp,
            c,
            i,
            n,
            total,
            round(pct_c, 2),
            round(pct_i, 2),
            round(pct_n, 2),
        ])

    csv_data = output.getvalue()
    output.close()

    html_parts = [
        '<!doctype html><html><head><meta charset="utf-8"><title>Ficha de Observación</title>',
        '<style>body{font-family:Arial,sans-serif;background:#fff;color:#111;padding:24px} table{border-collapse:collapse;width:100%;margin-top:16px} th,td{border:1px solid #333;padding:8px;font-size:12px;text-align:center} th{background:#eaeaea} .left{text-align:left} .img{max-width:100%;border:1px solid #ccc;margin-top:8px} .page{page-break-after:always}</style>',
        '</head><body>',
        '<h2>Ficha de Observación Automática</h2>',
        f'<p><b>Video:</b> {video_info["filename"]}<br><b>Observaciones:</b> {len(observations)}</p>',
        '<h3>Tabla Resumen</h3>',
        '<table><thead><tr><th>Tipo de EPP</th><th>Uso correcto (C)</th><th>Uso incorrecto (I)</th><th>No uso (N)</th><th>Total</th><th>% C</th><th>% I</th><th>% N</th></tr></thead><tbody>'
    ]
    for epp in epps:
        total = summary[epp]['C'] + summary[epp]['I'] + summary[epp]['N']
        pct_c = (summary[epp]['C'] / total * 100) if total else 0
        pct_i = (summary[epp]['I'] / total * 100) if total else 0
        pct_n = (summary[epp]['N'] / total * 100) if total else 0
        html_parts.append(
            f'<tr><td class="left">{epp.capitalize()}</td><td>{summary[epp]["C"]}</td><td>{summary[epp]["I"]}</td><td>{summary[epp]["N"]}</td><td>{total}</td><td>{pct_c:.2f}%</td><td>{pct_i:.2f}%</td><td>{pct_n:.2f}%</td></tr>'
        )
    html_parts.append('</tbody></table>')

    for obs in observations:
        capture_index = obs.get('capture_index', 0)
        html_parts.append('<div class="page">')
        html_parts.append(f'<h3>Captura {capture_index} - Frame {obs.get("frame_number")}</h3>')
        html_parts.append(f'<p><b>Estado:</b> {obs.get("estado")}<br><b>Mensaje:</b> {obs.get("mensaje", "")}</p>')
        html_parts.append('<table><thead><tr><th>Casco</th><th>Chaleco</th><th>Guantes</th><th>Botas</th><th>Gafas</th></tr></thead><tbody><tr>')
        pos = obs.get('epp_positioning', {}) or {}
        for epp in epps:
            html_parts.append(f'<td>{pos.get(epp, "ausente")}</td>')
        html_parts.append('</tr></tbody></table>')
        html_parts.append(f'<img class="img" src="frames/capture_{capture_index}_frame_{obs.get("frame_number")}.jpg" alt="Captura {capture_index} - Frame {obs.get("frame_number")}">')
        html_parts.append('</div>')

    html_parts.append('</body></html>')
    html_report = ''.join(html_parts)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('ficha_observacion.html', html_report)
        zf.writestr('observaciones.csv', csv_data)
        for obs in observations:
            snapshot_bytes = obs.get('snapshot_bytes')
            if snapshot_bytes:
                capture_index = obs.get('capture_index', 0)
                zf.writestr(f'frames/capture_{capture_index}_frame_{obs.get("frame_number")}.jpg', snapshot_bytes)

    zip_buffer.seek(0)
    filename = f'ficha_observacion_{video_id}.zip'
    return Response(
        content=zip_buffer.getvalue(),
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


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


# ==================== EVALUACIÓN FI-PS ====================

class AnotacionManualRequest(BaseModel):
    video_id: str
    frame_number: int
    casco: int  # 1=presente, 0=ausente
    chaleco: int
    guantes: int
    botas: int
    gafas: int
    notas: str = ""

@router.post("/annotations/save")
async def save_annotation(request: AnotacionManualRequest):
    """Guarda una anotación manual del usuario (ground truth)"""
    from backend.core.database import SessionLocal, AnotacionManual
    
    db = SessionLocal()
    try:
        # Guardar anotación
        anotacion = AnotacionManual(
            video_id=request.video_id,
            frame_number=request.frame_number,
            casco_manual=request.casco,
            chaleco_manual=request.chaleco,
            guantes_manual=request.guantes,
            botas_manual=request.botas,
            gafas_manual=request.gafas,
            notas=request.notas,
            anotado_por="Evaluador"
        )
        db.add(anotacion)
        db.commit()
        
        return {
            "success": True,
            "annotation_id": anotacion.id,
            "message": f"Anotación guardada para frame {request.frame_number}"
        }
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error guardando anotación: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@router.get("/annotations/{video_id}")
async def get_annotations(video_id: str):
    """Obtiene todas las anotaciones de un video"""
    from backend.core.database import SessionLocal, AnotacionManual
    
    db = SessionLocal()
    try:
        anotaciones = db.query(AnotacionManual).filter(
            AnotacionManual.video_id == video_id
        ).order_by(AnotacionManual.frame_number).all()
        
        result = []
        for a in anotaciones:
            result.append({
                "id": a.id,
                "frame_number": a.frame_number,
                "casco": a.casco_manual,
                "chaleco": a.chaleco_manual,
                "guantes": a.guantes_manual,
                "botas": a.botas_manual,
                "gafas": a.gafas_manual,
                "notas": a.notas,
                "timestamp": a.anotacion_fecha.strftime('%H:%M:%S') if a.anotacion_fecha else ''
            })
        
        return {"success": True, "annotations": result}
    except Exception as e:
        print(f"[ERROR] Error obteniendo anotaciones: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@router.get("/annotations/{video_id}/download")
async def download_annotations(video_id: str):
    """Descarga las anotaciones manuales de un video en formato CSV."""
    from backend.core.database import SessionLocal, AnotacionManual

    db = SessionLocal()
    try:
        anotaciones = db.query(AnotacionManual).filter(
            AnotacionManual.video_id == video_id
        ).order_by(AnotacionManual.frame_number).all()

        if not anotaciones:
            raise HTTPException(status_code=404, detail="No hay anotaciones para este video")

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id",
            "video_id",
            "frame_number",
            "timestamp",
            "casco",
            "chaleco",
            "guantes",
            "botas",
            "gafas",
            "notas",
            "anotacion_fecha",
            "anotado_por",
        ])

        for a in anotaciones:
            writer.writerow([
                a.id,
                a.video_id,
                a.frame_number,
                a.timestamp.strftime('%Y-%m-%d %H:%M:%S') if a.timestamp else '',
                a.casco_manual,
                a.chaleco_manual,
                a.guantes_manual,
                a.botas_manual,
                a.gafas_manual,
                a.notas or '',
                a.anotacion_fecha.strftime('%Y-%m-%d %H:%M:%S') if a.anotacion_fecha else '',
                a.anotado_por or '',
            ])

        csv_data = output.getvalue()
        output.close()

        filename = f"anotaciones_{video_id}.csv"
        return Response(
            content=csv_data,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    finally:
        db.close()

@router.post("/evaluations/calculate-fips/{video_id}")
async def calculate_fips(video_id: str, nombre_evaluador: str = "Evaluador"):
    """Calcula las métricas FI-PS comparando anotaciones manuales con detecciones"""
    from backend.core.database import SessionLocal, AnotacionManual, EvaluacionFIPS
    
    db = SessionLocal()
    try:
        # Obtener todas las anotaciones del video
        anotaciones = db.query(AnotacionManual).filter(
            AnotacionManual.video_id == video_id
        ).all()
        
        if not anotaciones:
            return {"success": False, "error": "No hay anotaciones para este video"}
        
        # Inicializar contadores por EPP
        epps = ['casco', 'chaleco', 'guantes', 'botas', 'gafas']
        metricas = {}
        
        for epp in epps:
            metricas[epp] = {
                'vp': 0,  # Verdaderos positivos
                'fp': 0,  # Falsos positivos
                'vn': 0,  # Verdaderos negativos
                'fn': 0   # Falsos negativos
            }
        
        # Comparar cada anotación con lo que detectó el sistema
        for anotacion in anotaciones:
            # Obtener lo que el sistema detectó en ese frame
            # Por ahora, asumimos que tenemos acceso a active_videos
            # En una implementación real, buscarías en la BD
            
            # Mapear anotaciones manuales
            manual = {
                'casco': anotacion.casco_manual,
                'chaleco': anotacion.chaleco_manual,
                'guantes': anotacion.guantes_manual,
                'botas': anotacion.botas_manual,
                'gafas': anotacion.gafas_manual
            }
            
            # TODO: Obtener detecciones del sistema para este frame
            # Por ahora, usaremos valores de demostración
            sistema = {
                'casco': 1,  # El sistema detectó casco
                'chaleco': 1,
                'guantes': 0,
                'botas': 1,
                'gafas': 0
            }
            
            # Calcular VP, FP, VN, FN por EPP
            for epp in epps:
                manual_val = manual.get(epp, 0)
                sistema_val = sistema.get(epp, 0)
                
                if manual_val == 1 and sistema_val == 1:
                    # Verdadero Positivo: ambos detectan
                    metricas[epp]['vp'] += 1
                elif manual_val == 0 and sistema_val == 1:
                    # Falso Positivo: sistema dice que hay pero no hay
                    metricas[epp]['fp'] += 1
                elif manual_val == 0 and sistema_val == 0:
                    # Verdadero Negativo: ambos concordar en ausencia
                    metricas[epp]['vn'] += 1
                elif manual_val == 1 and sistema_val == 0:
                    # Falso Negativo: el sistema no lo detecta
                    metricas[epp]['fn'] += 1
        
        # Calcular Precisión y Sensibilidad
        for epp in epps:
            vp = metricas[epp]['vp']
            fp = metricas[epp]['fp']
            fn = metricas[epp]['fn']
            
            # Precisión = VP / (VP + FP) * 100
            if (vp + fp) > 0:
                metricas[epp]['precision'] = (vp / (vp + fp)) * 100
            else:
                metricas[epp]['precision'] = 0
            
            # Sensibilidad = VP / (VP + FN) * 100
            if (vp + fn) > 0:
                metricas[epp]['sensibilidad'] = (vp / (vp + fn)) * 100
            else:
                metricas[epp]['sensibilidad'] = 0
        
        # Crear reporte FI-PS
        evaluacion = EvaluacionFIPS(
            video_id=video_id,
            nombre_evaluador=nombre_evaluador,
            # Casco
            casco_vp=metricas['casco']['vp'],
            casco_fp=metricas['casco']['fp'],
            casco_vn=metricas['casco']['vn'],
            casco_fn=metricas['casco']['fn'],
            casco_precision=metricas['casco']['precision'],
            casco_sensibilidad=metricas['casco']['sensibilidad'],
            # Chaleco
            chaleco_vp=metricas['chaleco']['vp'],
            chaleco_fp=metricas['chaleco']['fp'],
            chaleco_vn=metricas['chaleco']['vn'],
            chaleco_fn=metricas['chaleco']['fn'],
            chaleco_precision=metricas['chaleco']['precision'],
            chaleco_sensibilidad=metricas['chaleco']['sensibilidad'],
            # Guantes
            guantes_vp=metricas['guantes']['vp'],
            guantes_fp=metricas['guantes']['fp'],
            guantes_vn=metricas['guantes']['vn'],
            guantes_fn=metricas['guantes']['fn'],
            guantes_precision=metricas['guantes']['precision'],
            guantes_sensibilidad=metricas['guantes']['sensibilidad'],
            # Botas
            botas_vp=metricas['botas']['vp'],
            botas_fp=metricas['botas']['fp'],
            botas_vn=metricas['botas']['vn'],
            botas_fn=metricas['botas']['fn'],
            botas_precision=metricas['botas']['precision'],
            botas_sensibilidad=metricas['botas']['sensibilidad'],
            # Gafas
            gafas_vp=metricas['gafas']['vp'],
            gafas_fp=metricas['gafas']['fp'],
            gafas_vn=metricas['gafas']['vn'],
            gafas_fn=metricas['gafas']['fn'],
            gafas_precision=metricas['gafas']['precision'],
            gafas_sensibilidad=metricas['gafas']['sensibilidad'],
            # Resumen
            precision_promedio=sum([m['precision'] for m in metricas.values()]) / len(epps),
            sensibilidad_promedio=sum([m['sensibilidad'] for m in metricas.values()]) / len(epps),
            total_momentos_anotados=len(anotaciones)
        )
        
        db.add(evaluacion)
        db.commit()
        
        return {
            "success": True,
            "evaluacion_id": evaluacion.id,
            "metricas": metricas,
            "precision_promedio": evaluacion.precision_promedio,
            "sensibilidad_promedio": evaluacion.sensibilidad_promedio,
            "total_momentos_anotados": len(anotaciones)
        }
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error calculando FI-PS: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@router.get("/evaluations/{video_id}")
async def get_evaluation(video_id: str):
    """Obtiene el reporte FI-PS de un video"""
    from backend.core.database import SessionLocal, EvaluacionFIPS
    
    db = SessionLocal()
    try:
        evaluacion = db.query(EvaluacionFIPS).filter(
            EvaluacionFIPS.video_id == video_id
        ).order_by(EvaluacionFIPS.fecha_evaluacion.desc()).first()
        
        if not evaluacion:
            return {"success": False, "error": "No hay evaluación para este video"}
        
        result = {
            "id": evaluacion.id,
            "video_id": evaluacion.video_id,
            "nombre_evaluador": evaluacion.nombre_evaluador,
            "fecha": evaluacion.fecha_evaluacion.strftime('%d/%m/%Y %H:%M:%S'),
            "total_momentos": evaluacion.total_momentos_anotados,
            "precision_promedio": round(evaluacion.precision_promedio, 2),
            "sensibilidad_promedio": round(evaluacion.sensibilidad_promedio, 2),
            "metricas_por_epp": {
                "casco": {
                    "vp": evaluacion.casco_vp,
                    "fp": evaluacion.casco_fp,
                    "vn": evaluacion.casco_vn,
                    "fn": evaluacion.casco_fn,
                    "precision": round(evaluacion.casco_precision, 2),
                    "sensibilidad": round(evaluacion.casco_sensibilidad, 2)
                },
                "chaleco": {
                    "vp": evaluacion.chaleco_vp,
                    "fp": evaluacion.chaleco_fp,
                    "vn": evaluacion.chaleco_vn,
                    "fn": evaluacion.chaleco_fn,
                    "precision": round(evaluacion.chaleco_precision, 2),
                    "sensibilidad": round(evaluacion.chaleco_sensibilidad, 2)
                },
                "guantes": {
                    "vp": evaluacion.guantes_vp,
                    "fp": evaluacion.guantes_fp,
                    "vn": evaluacion.guantes_vn,
                    "fn": evaluacion.guantes_fn,
                    "precision": round(evaluacion.guantes_precision, 2),
                    "sensibilidad": round(evaluacion.guantes_sensibilidad, 2)
                },
                "botas": {
                    "vp": evaluacion.botas_vp,
                    "fp": evaluacion.botas_fp,
                    "vn": evaluacion.botas_vn,
                    "fn": evaluacion.botas_fn,
                    "precision": round(evaluacion.botas_precision, 2),
                    "sensibilidad": round(evaluacion.botas_sensibilidad, 2)
                },
                "gafas": {
                    "vp": evaluacion.gafas_vp,
                    "fp": evaluacion.gafas_fp,
                    "vn": evaluacion.gafas_vn,
                    "fn": evaluacion.gafas_fn,
                    "precision": round(evaluacion.gafas_precision, 2),
                    "sensibilidad": round(evaluacion.gafas_sensibilidad, 2)
                }
            }
        }
        
        return {"success": True, "evaluacion": result}
    except Exception as e:
        print(f"[ERROR] Error obteniendo evaluación: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

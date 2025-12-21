"""
Gestor de Alertas y Detecciones
Guarda detecciones en base de datos y genera alertas cuando hay incumplimiento
"""
from typing import Dict, List
from datetime import datetime
from sqlalchemy.orm import Session
from backend.core.database import SessionLocal, Deteccion, DeteccionEPP, Alerta, TipoEPP

class AlertManager:
    def __init__(self):
        self.epp_mapping = {
            'casco': 1,
            'chaleco': 2,
            'guantes': 3,
            'botas': 4,
            'gafas': 5
        }
    
    def _get_db(self) -> Session:
        """Obtiene sesión de base de datos"""
        return SessionLocal()
    
    def save_detection(self, camera_id: int, detections: List[Dict], compliance: Dict, frame=None) -> int:
        """
        Guarda una detección en la base de datos
        
        Args:
            camera_id: ID de la cámara
            detections: Lista de detecciones del detector EPP
            compliance: Resultado de clasificación de cumplimiento
            frame: Frame de imagen (opcional, para guardar snapshot)
            
        Returns:
            ID de la detección guardada
        """
        db = self._get_db()
        try:
            # Guardar imagen si se proporcionó frame y hay incumplimiento
            imagen_path = None
            if frame is not None and compliance['estado'] != 'C':
                import cv2
                import os
                from datetime import datetime
                
                # Crear carpeta de snapshots si no existe (ruta absoluta)
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                snapshots_dir = os.path.join(project_root, "backend", "static", "snapshots")
                os.makedirs(snapshots_dir, exist_ok=True)
                
                # Generar nombre de archivo con timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"cam{camera_id}_{timestamp}.jpg"
                full_path = os.path.join(snapshots_dir, filename)
                
                # Guardar imagen
                cv2.imwrite(full_path, frame)
                
                # Guardar ruta relativa para la BD (para servir vía /static/)
                imagen_path = f"static/snapshots/{filename}"
                print(f"[ALERT] Snapshot guardado: {full_path}")
            
            # Crear registro de detección principal
            deteccion = Deteccion(
                camera_id=camera_id,
                trabajador_id=None,  # Por ahora sin reconocimiento de trabajador
                timestamp=datetime.now(),
                estado_epp=compliance['estado'],
                observaciones=compliance['mensaje'],
                imagen_path=imagen_path
            )
            
            db.add(deteccion)
            db.flush()  # Para obtener el ID
            
            # Guardar cada EPP detectado
            for epp_type, present in compliance['epp_status'].items():
                # Buscar detecciones de este tipo de EPP
                epp_detections = [d for d in detections if d['epp_type'] == epp_type]
                
                tipo_epp_id = self.epp_mapping.get(epp_type)
                if not tipo_epp_id:
                    continue
                
                if epp_detections:
                    # Se detectó este EPP
                    for det in epp_detections:
                        deteccion_epp = DeteccionEPP(
                            deteccion_id=deteccion.id,
                            tipo_epp_id=tipo_epp_id,
                            detectado=1 if det['has_epp'] else 0,
                            confianza=det['confidence'],
                            uso_correcto=1 if det['has_epp'] else 0,
                            bbox_x=det['bbox'][0],
                            bbox_y=det['bbox'][1],
                            bbox_width=det['bbox'][2] - det['bbox'][0],
                            bbox_height=det['bbox'][3] - det['bbox'][1]
                        )
                        db.add(deteccion_epp)
                else:
                    # No se detectó este EPP
                    deteccion_epp = DeteccionEPP(
                        deteccion_id=deteccion.id,
                        tipo_epp_id=tipo_epp_id,
                        detectado=0,
                        confianza=0.0,
                        uso_correcto=0
                    )
                    db.add(deteccion_epp)
            
            db.commit()
            return deteccion.id
            
        except Exception as e:
            db.rollback()
            print(f"[ALERT ERROR] Error guardando detección: {e}")
            return None
        finally:
            db.close()
    
    def generate_alert(self, camera_id: int, deteccion_id: int, compliance: Dict) -> int:
        """
        Genera una alerta si hay incumplimiento de EPP
        
        Args:
            camera_id: ID de la cámara
            deteccion_id: ID de la detección
            compliance: Resultado de clasificación
            
        Returns:
            ID de la alerta generada o None
        """
        # Solo generar alertas si el estado NO es Correcto
        if compliance['estado'] == 'C':
            return None
        
        db = self._get_db()
        try:
            # Determinar tipo y severidad
            if compliance['estado'] == 'N':
                tipo = 'sin_epp'
                severidad = 'critica'
                mensaje = 'Trabajador sin EPP detectado'
            else:  # Estado 'I'
                # Determinar qué EPP falta
                missing = [epp for epp, present in compliance['epp_status'].items() if not present]
                
                # Severidad según EPP faltante
                if 'casco' in missing:
                    tipo = 'sin_casco'
                    severidad = 'critica'
                elif 'chaleco' in missing:
                    tipo = 'sin_chaleco'
                    severidad = 'alta'
                elif len(missing) >= 3:
                    tipo = 'epp_multiple_faltante'
                    severidad = 'alta'
                else:
                    tipo = 'epp_incorrecto'
                    severidad = 'media'
                
                mensaje = f"EPP incorrecto: Falta {', '.join(missing)}"
            
            # Crear alerta
            alerta = Alerta(
                deteccion_id=deteccion_id,
                camera_id=camera_id,
                timestamp=datetime.now(),
                tipo=tipo,
                severidad=severidad,
                mensaje=mensaje,
                estado='pendiente'
            )
            
            db.add(alerta)
            db.commit()
            
            print(f"[ALERT] Generada alerta {severidad.upper()}: {mensaje} (Cámara {camera_id})")
            return alerta.id
            
        except Exception as e:
            db.rollback()
            print(f"[ALERT ERROR] Error generando alerta: {e}")
            return None
        finally:
            db.close()
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Obtiene las alertas más recientes"""
        db = self._get_db()
        try:
            alertas = db.query(Alerta).order_by(Alerta.timestamp.desc()).limit(limit).all()
            
            result = []
            for alerta in alertas:
                result.append({
                    'id': alerta.id,
                    'camera_id': alerta.camera_id,
                    'camera_nombre': alerta.camera.nombre if alerta.camera else 'Desconocida',
                    'zona': alerta.camera.zona if alerta.camera else '',
                    'timestamp': alerta.timestamp.strftime('%H:%M %p') if alerta.timestamp else '',
                    'fecha': alerta.timestamp.strftime('%Y-%m-%d') if alerta.timestamp else '',
                    'tipo': alerta.tipo,
                    'severidad': alerta.severidad,
                    'mensaje': alerta.mensaje,
                    'estado': alerta.estado
                })
            
            return result
            
        except Exception as e:
            print(f"[ALERT ERROR] Error obteniendo alertas: {e}")
            return []
        finally:
            db.close()
    
    def get_alerts_count(self, estado: str = 'pendiente') -> int:
        """Obtiene el conteo de alertas por estado"""
        db = self._get_db()
        try:
            count = db.query(Alerta).filter(Alerta.estado == estado).count()
            return count
        except Exception as e:
            print(f"[ALERT ERROR] Error contando alertas: {e}")
            return 0
        finally:
            db.close()

# Instancia global
alert_manager = AlertManager()

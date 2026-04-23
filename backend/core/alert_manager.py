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
            # No guardar en BD cuando no hay persona detectada.
            if compliance.get('estado') == 'P':
                return None

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
            epp_positioning = compliance.get('epp_positioning', {})
            for epp_type, present in compliance['epp_status'].items():
                # Buscar detecciones de este tipo de EPP
                epp_detections = [d for d in detections if d['epp_type'] == epp_type]
                best_detection = max(epp_detections, key=lambda d: d.get('confidence', 0.0), default=None)
                
                tipo_epp_id = self.epp_mapping.get(epp_type)
                if not tipo_epp_id:
                    continue

                positioning_state = epp_positioning.get(epp_type, 'ausente')
                detectado_val = 1 if positioning_state in ('correcto', 'incorrecto') else 0
                uso_correcto_val = 1 if positioning_state == 'correcto' else 0
                confianza_val = best_detection.get('confidence', 0.0) if best_detection else 0.0
                bbox = best_detection.get('bbox') if best_detection else None
                
                deteccion_epp = DeteccionEPP(
                    deteccion_id=deteccion.id,
                    tipo_epp_id=tipo_epp_id,
                    detectado=detectado_val,
                    confianza=confianza_val,
                    uso_correcto=uso_correcto_val,
                    bbox_x=bbox[0] if bbox else None,
                    bbox_y=bbox[1] if bbox else None,
                    bbox_width=(bbox[2] - bbox[0]) if bbox else None,
                    bbox_height=(bbox[3] - bbox[1]) if bbox else None
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
        # Solo generar alertas para incumplimientos reales (I/N)
        if compliance.get('estado') in ('C', 'P'):
            return None
        
        db = self._get_db()
        try:
            # Determinar tipo y severidad
            if compliance['estado'] == 'N':
                tipo = 'sin_epp'
                severidad = 'critica'
                mensaje = 'Trabajador sin EPP detectado'
            else:  # Estado 'I'
                missing = compliance.get('missing_epp')
                incorrectly_positioned = compliance.get('incorrectly_positioned', [])

                if missing is None:
                    missing = [epp for epp, present in compliance['epp_status'].items() if not present]

                # Severidad según faltantes/mal uso
                if 'casco' in missing:
                    tipo = 'sin_casco'
                    severidad = 'critica'
                elif 'chaleco' in missing:
                    tipo = 'sin_chaleco'
                    severidad = 'alta'
                elif len(missing) >= 3:
                    tipo = 'epp_multiple_faltante'
                    severidad = 'alta'
                elif incorrectly_positioned:
                    tipo = 'epp_mal_uso'
                    severidad = 'media'
                else:
                    tipo = 'epp_incorrecto'
                    severidad = 'media'

                partes = []
                if incorrectly_positioned:
                    partes.append(f"Mal puesto: {', '.join(incorrectly_positioned)}")
                if missing:
                    partes.append(f"Falta: {', '.join(missing)}")
                mensaje = "EPP incorrecto: " + (" | ".join(partes) if partes else "Uso incorrecto")
            
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

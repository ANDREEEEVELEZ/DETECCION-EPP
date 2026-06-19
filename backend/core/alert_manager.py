"""
Gestor de Alertas y Detecciones
Guarda detecciones en base de datos y genera alertas cuando hay incumplimiento
"""
from typing import Dict, List, Optional
from datetime import datetime
import mimetypes
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from sqlalchemy.orm import Session
from backend.core.database import SessionLocal, Camera, Deteccion, DeteccionEPP, Alerta, TipoEPP

class AlertManager:
    def __init__(self):
        self.epp_mapping = {
            'casco': 1,
            'chaleco': 2,
            'guantes': 3,
            'botas': 4,
            'gafas': 5
        }

        self.email_alerts_enabled = os.getenv("EMAIL_ALERTS_ENABLED", "0").lower() in ("1", "true", "yes", "on")
        self.smtp_host = os.getenv("SMTP_HOST", "").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "").strip()
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from = os.getenv("SMTP_FROM", self.smtp_user or "alertas@localhost").strip()
        self.smtp_to = [email.strip() for email in os.getenv("ALERT_EMAIL_TO", "").split(",") if email.strip()]
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "1").lower() in ("1", "true", "yes", "on")
    
    def _get_db(self) -> Session:
        """Obtiene sesión de base de datos"""
        return SessionLocal()

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _resolve_snapshot_path(self, imagen_path: Optional[str]) -> Optional[Path]:
        if not imagen_path:
            return None

        relative_path = Path(imagen_path)
        if relative_path.is_absolute():
            return relative_path if relative_path.exists() else None

        candidate = self._project_root() / "backend" / relative_path
        return candidate if candidate.exists() else None

    def _build_email_message(self, camera_nombre: str, camera_zona: str, alerta: Alerta, compliance: Dict, attachment_paths: List[Path]) -> Optional[EmailMessage]:
        if not self.email_alerts_enabled:
            return None

        if not self.smtp_host or not self.smtp_to:
            print("[ALERT EMAIL] Configuración SMTP incompleta; se omite el envío por correo")
            return None

        fecha_evento = alerta.timestamp.strftime("%Y-%m-%d %H:%M:%S") if alerta.timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if compliance.get("estado") == "N":
            asunto_estado = "EPP nulo"
            descripcion = "Se detectó personal sin EPP."
        else:
            asunto_estado = "EPP mal puesto o incompleto"
            descripcion = "Se detectó personal con EPP mal colocado o incompleto."

        mensaje = EmailMessage()
        mensaje["Subject"] = f"[VISION_EPP] {asunto_estado} - {camera_nombre}"
        mensaje["From"] = self.smtp_from
        mensaje["To"] = ", ".join(self.smtp_to)

        cuerpo = [
            "Alerta automática de incumplimiento de EPP.",
            "",
            descripcion,
            f"Estado detectado: {compliance.get('estado', 'N/A')}",
            f"Mensaje: {compliance.get('mensaje', alerta.mensaje or 'Sin detalle')}",
            f"Cámara: {camera_nombre}",
            f"Ubicación: {camera_zona}",
            f"Fecha y hora: {fecha_evento}",
            f"Severidad: {alerta.severidad}",
            f"Tipo de alerta: {alerta.tipo}",
            "",
            "Evidencias adjuntas en imagen.",
        ]
        mensaje.set_content("\n".join(cuerpo))

        for attachment_path in attachment_paths:
            mime_type, _ = mimetypes.guess_type(str(attachment_path))
            if mime_type:
                main_type, sub_type = mime_type.split("/", 1)
            else:
                main_type, sub_type = "application", "octet-stream"

            with open(attachment_path, "rb") as file_handle:
                mensaje.add_attachment(
                    file_handle.read(),
                    maintype=main_type,
                    subtype=sub_type,
                    filename=attachment_path.name,
                )

        return mensaje

    def _send_email_alert(self, camera_nombre: str, camera_zona: str, imagen_path: Optional[str], alerta: Alerta, compliance: Dict) -> None:
        attachment_paths: List[Path] = []
        snapshot_path = self._resolve_snapshot_path(imagen_path)
        if snapshot_path is not None:
            attachment_paths.append(snapshot_path)

        mensaje = self._build_email_message(camera_nombre, camera_zona, alerta, compliance, attachment_paths)
        if mensaje is None:
            return

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as smtp:
                if self.smtp_use_tls:
                    smtp.starttls()
                if self.smtp_user:
                    smtp.login(self.smtp_user, self.smtp_password)
                smtp.send_message(mensaje)

            print(f"[ALERT EMAIL] Correo enviado para alerta {alerta.id} a {', '.join(self.smtp_to)}")
        except Exception as e:
            print(f"[ALERT EMAIL ERROR] No se pudo enviar el correo de alerta: {e}")
    
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
                mensaje = 'Trabajadores no portan EPP (EPP nulo)'
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
                mensaje = "Trabajadores no portan EPP correctamente: " + (" | ".join(partes) if partes else "Uso incorrecto")
            
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
            db.refresh(alerta)

            camera = db.query(Camera).filter(Camera.id == camera_id).first()
            deteccion = db.query(Deteccion).filter(Deteccion.id == deteccion_id).first()

            if deteccion is not None and camera is not None:
                print(f"[ALERT EMAIL] Preparando envío para alerta {alerta.id} | camera={camera.nombre} | zona={camera.zona} | estado={compliance.get('estado')}")
                self._send_email_alert(
                    camera_nombre=camera.nombre,
                    camera_zona=camera.zona,
                    imagen_path=deteccion.imagen_path,
                    alerta=alerta,
                    compliance=compliance,
                )
            
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

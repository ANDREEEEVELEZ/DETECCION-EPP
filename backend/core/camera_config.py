"""
Módulo de gestión de configuración de cámaras
Almacena la asignación de cámaras físicas a zonas en MySQL
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

class CameraConfigManager:
    def __init__(self):
        pass
    
    def _get_db(self) -> Session:
        """Obtiene una sesión de base de datos"""
        from .database import SessionLocal
        return SessionLocal()
    
    def get_all_cameras(self) -> List[Dict]:
        """Obtiene todas las cámaras configuradas"""
        db = self._get_db()
        try:
            from .database import Camera
            cameras = db.query(Camera).all()
            return [{
                'id': cam.id,
                'physical_id': cam.physical_id,
                'nombre': cam.nombre,
                'zona': cam.zona,
                'estado': cam.estado,
                'resolucion': cam.resolucion
            } for cam in cameras]
        finally:
            db.close()
    
    def add_camera(self, physical_id: int, nombre: str, zona: str) -> Dict:
        """Agrega una nueva cámara configurada"""
        db = self._get_db()
        try:
            from .database import Camera
            
            # Verificar que no exista ya esta cámara física
            existing = db.query(Camera).filter_by(physical_id=physical_id).first()
            if existing:
                raise ValueError(f"La cámara física {physical_id} ya está configurada")
            
            # Crear nueva cámara
            new_camera = Camera(
                physical_id=physical_id,
                nombre=nombre,
                zona=zona,
                estado='activa',
                resolucion='1280x720',
                created_at=datetime.now()
            )
            
            db.add(new_camera)
            db.commit()
            db.refresh(new_camera)
            
            return {
                'id': new_camera.id,
                'physical_id': new_camera.physical_id,
                'nombre': new_camera.nombre,
                'zona': new_camera.zona,
                'estado': new_camera.estado,
                'resolucion': new_camera.resolucion
            }
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def remove_camera(self, camera_id: int) -> bool:
        """Elimina una cámara configurada por su ID"""
        db = self._get_db()
        try:
            from .database import Camera
            camera = db.query(Camera).filter_by(id=camera_id).first()
            
            if not camera:
                return False
            
            db.delete(camera)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def update_camera(self, camera_id: int, nombre: str, zona: str) -> Optional[Dict]:
        """Actualiza los datos de una cámara configurada"""
        db = self._get_db()
        try:
            from .database import Camera
            camera = db.query(Camera).filter_by(id=camera_id).first()
            
            if not camera:
                return None
            
            camera.nombre = nombre
            camera.zona = zona
            db.commit()
            db.refresh(camera)
            
            return {
                'id': camera.id,
                'physical_id': camera.physical_id,
                'nombre': camera.nombre,
                'zona': camera.zona,
                'estado': camera.estado,
                'resolucion': camera.resolucion
            }
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_camera_by_id(self, camera_id: int) -> Optional[Dict]:
        """Obtiene una cámara por su ID"""
        db = self._get_db()
        try:
            from .database import Camera
            camera = db.query(Camera).filter_by(id=camera_id).first()
            
            if not camera:
                return None
            
            return {
                'id': camera.id,
                'physical_id': camera.physical_id,
                'nombre': camera.nombre,
                'zona': camera.zona,
                'estado': camera.estado,
                'resolucion': camera.resolucion
            }
        finally:
            db.close()

# Instancia global
camera_manager = CameraConfigManager()

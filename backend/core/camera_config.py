"""
Módulo de gestión de configuración de cámaras
Almacena la asignación de cámaras físicas a zonas
"""
import json
import os
from typing import Dict, List, Optional
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "data" / "cameras_config.json"

class CameraConfigManager:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """Crea el directorio data si no existe"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            self._save_config([])
    
    def _load_config(self) -> List[Dict]:
        """Carga la configuración desde el archivo JSON"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_config(self, config: List[Dict]):
        """Guarda la configuración en el archivo JSON"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def get_all_cameras(self) -> List[Dict]:
        """Obtiene todas las cámaras configuradas"""
        return self._load_config()
    
    def add_camera(self, physical_id: int, nombre: str, zona: str) -> Dict:
        """Agrega una nueva cámara configurada"""
        config = self._load_config()
        
        # Verificar que no exista ya esta cámara física
        for cam in config:
            if cam['physical_id'] == physical_id:
                raise ValueError(f"La cámara física {physical_id} ya está configurada")
        
        # Generar ID único
        new_id = max([cam['id'] for cam in config], default=0) + 1
        
        new_camera = {
            'id': new_id,
            'physical_id': physical_id,
            'nombre': nombre,
            'zona': zona,
            'estado': 'activa',
            'resolucion': '1280x720'
        }
        
        config.append(new_camera)
        self._save_config(config)
        return new_camera
    
    def remove_camera(self, camera_id: int) -> bool:
        """Elimina una cámara configurada por su ID"""
        config = self._load_config()
        new_config = [cam for cam in config if cam['id'] != camera_id]
        
        if len(new_config) == len(config):
            return False  # No se encontró la cámara
        
        self._save_config(new_config)
        return True
    
    def update_camera(self, camera_id: int, nombre: str, zona: str) -> Optional[Dict]:
        """Actualiza los datos de una cámara configurada"""
        config = self._load_config()
        
        for cam in config:
            if cam['id'] == camera_id:
                cam['nombre'] = nombre
                cam['zona'] = zona
                self._save_config(config)
                return cam
        
        return None
    
    def get_camera_by_id(self, camera_id: int) -> Optional[Dict]:
        """Obtiene una cámara por su ID"""
        config = self._load_config()
        for cam in config:
            if cam['id'] == camera_id:
                return cam
        return None

# Instancia global
camera_manager = CameraConfigManager()

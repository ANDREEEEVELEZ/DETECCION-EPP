"""
Configuración de Base de Datos MySQL
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración de conexión
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "vision_epp")

DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ============= MODELOS =============

class Camera(Base):
    """Cámaras configuradas en el sistema"""
    __tablename__ = "cameras"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    physical_id = Column(Integer, unique=True, nullable=False)  # ID físico de Windows
    nombre = Column(String(100), nullable=False)
    zona = Column(String(100), nullable=False)
    estado = Column(String(20), default="activa")  # activa, inactiva, error
    resolucion = Column(String(20), default="1280x720")
    created_at = Column(DateTime, default=datetime.now)
    
    # Relaciones
    detecciones = relationship("Deteccion", back_populates="camera")
    alertas = relationship("Alerta", back_populates="camera")

class TipoEPP(Base):
    """Tipos de EPP que se pueden detectar"""
    __tablename__ = "tipos_epp"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50), nullable=False)  # Casco, Chaleco, Botas, etc.
    descripcion = Column(String(200))
    color_hex = Column(String(7))  # Color para UI (#FF5733)
    obligatorio = Column(Integer, default=1)  # 1=obligatorio, 0=opcional
    
    # Relaciones
    detecciones_epp = relationship("DeteccionEPP", back_populates="tipo_epp")

class Trabajador(Base):
    """Trabajadores/Personal registrado"""
    __tablename__ = "trabajadores"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre_completo = Column(String(150), nullable=False)
    dni = Column(String(20), unique=True)
    cargo = Column(String(100))
    empresa = Column(String(100))
    telefono = Column(String(20))
    estado = Column(String(20), default="activo")  # activo, inactivo, suspendido
    created_at = Column(DateTime, default=datetime.now)
    
    # Relaciones
    detecciones = relationship("Deteccion", back_populates="trabajador")

class Deteccion(Base):
    """Detecciones de personas en las cámaras"""
    __tablename__ = "detecciones"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    trabajador_id = Column(Integer, ForeignKey("trabajadores.id"), nullable=True)  # Null si no identificado
    
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    confianza_persona = Column(Float)  # Confianza de detección de persona (0-1)
    
    # Coordenadas del bounding box de la persona
    bbox_x = Column(Integer)
    bbox_y = Column(Integer)
    bbox_width = Column(Integer)
    bbox_height = Column(Integer)
    
    # Snapshot de la detección
    imagen_path = Column(String(500))  # Ruta a imagen guardada
    
    # Estado general de EPP
    estado_epp = Column(Enum('C', 'I', 'N', name='estado_epp_enum'), nullable=False)
    # C = Correcto (todos los EPP OK)
    # I = Incorrecto (EPP mal usado o incompleto)
    # N = No uso (sin EPP)
    
    observaciones = Column(Text)
    
    # Relaciones
    camera = relationship("Camera", back_populates="detecciones")
    trabajador = relationship("Trabajador", back_populates="detecciones")
    epp_detectados = relationship("DeteccionEPP", back_populates="deteccion")
    alertas = relationship("Alerta", back_populates="deteccion")

class DeteccionEPP(Base):
    """Detalle de cada EPP detectado en una detección de persona"""
    __tablename__ = "detecciones_epp"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    deteccion_id = Column(Integer, ForeignKey("detecciones.id"), nullable=False)
    tipo_epp_id = Column(Integer, ForeignKey("tipos_epp.id"), nullable=False)
    
    detectado = Column(Integer, nullable=False)  # 1=detectado, 0=no detectado
    confianza = Column(Float)  # Confianza de la detección (0-1)
    uso_correcto = Column(Integer)  # 1=correcto, 0=incorrecto, NULL=no aplica
    
    # Coordenadas del bounding box del EPP
    bbox_x = Column(Integer)
    bbox_y = Column(Integer)
    bbox_width = Column(Integer)
    bbox_height = Column(Integer)
    
    # Relaciones
    deteccion = relationship("Deteccion", back_populates="epp_detectados")
    tipo_epp = relationship("TipoEPP", back_populates="detecciones_epp")

class Alerta(Base):
    """Alertas generadas por incumplimiento de EPP"""
    __tablename__ = "alertas"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    deteccion_id = Column(Integer, ForeignKey("detecciones.id"), nullable=False)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    tipo = Column(String(50), nullable=False)  # sin_casco, sin_chaleco, epp_incorrecto, etc.
    severidad = Column(Enum('baja', 'media', 'alta', 'critica', name='severidad_enum'), default='media')
    mensaje = Column(String(500))
    
    # Estado de la alerta
    estado = Column(String(20), default="pendiente")  # pendiente, revisada, resuelta, descartada
    revisada_por = Column(String(100))
    revisada_at = Column(DateTime)
    notas_revision = Column(Text)
    
    # Relaciones
    deteccion = relationship("Deteccion", back_populates="alertas")
    camera = relationship("Camera", back_populates="alertas")

class EventoSistema(Base):
    """Log de eventos del sistema"""
    __tablename__ = "eventos_sistema"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    tipo = Column(String(50))  # camara_conectada, camara_desconectada, error_modelo, etc.
    nivel = Column(Enum('info', 'warning', 'error', 'critical', name='nivel_enum'), default='info')
    mensaje = Column(Text)
    detalles = Column(Text)  # JSON con detalles adicionales

class ConfiguracionIA(Base):
    """Configuración de parámetros del modelo de IA"""
    __tablename__ = "configuracion_ia"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    parametro = Column(String(100), unique=True, nullable=False)
    valor = Column(String(500))
    descripcion = Column(String(500))
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

# ============= FUNCIONES AUXILIARES =============

def get_db():
    """Generador de sesión de base de datos"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Inicializa todas las tablas"""
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas creadas exitosamente")

def seed_initial_data():
    """Inserta datos iniciales"""
    db = SessionLocal()
    
    try:
        # Insertar tipos de EPP
        tipos_epp = [
            TipoEPP(nombre="Casco", descripcion="Casco de seguridad", color_hex="#FFD700", obligatorio=1),
            TipoEPP(nombre="Chaleco", descripcion="Chaleco reflectivo", color_hex="#FF6B35", obligatorio=1),
            TipoEPP(nombre="Guantes", descripcion="Guantes de trabajo", color_hex="#4ECDC4", obligatorio=1),
            TipoEPP(nombre="Botas", descripcion="Botas de seguridad", color_hex="#95E1D3", obligatorio=1),
            TipoEPP(nombre="Gafas", descripcion="Gafas de protección", color_hex="#38A3A5", obligatorio=0),
        ]
        
        for epp in tipos_epp:
            existing = db.query(TipoEPP).filter_by(nombre=epp.nombre).first()
            if not existing:
                db.add(epp)
        
        # Insertar configuración inicial de IA
        configs = [
            ConfiguracionIA(parametro="confianza_minima", valor="0.5", descripcion="Umbral mínimo de confianza para detecciones"),
            ConfiguracionIA(parametro="fps_procesamiento", valor="15", descripcion="Frames por segundo a procesar"),
            ConfiguracionIA(parametro="modelo_yolo", valor="yolov8n.pt", descripcion="Modelo YOLO a utilizar"),
            ConfiguracionIA(parametro="alertas_activas", valor="1", descripcion="Activar/desactivar generación de alertas"),
        ]
        
        for config in configs:
            existing = db.query(ConfiguracionIA).filter_by(parametro=config.parametro).first()
            if not existing:
                db.add(config)
        
        db.commit()
        print("✅ Datos iniciales insertados")
        
    except Exception as e:
        print(f"❌ Error insertando datos iniciales: {e}")
        db.rollback()
    finally:
        db.close()

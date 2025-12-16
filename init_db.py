"""
Script para inicializar la base de datos MySQL
Ejecutar: python init_db.py
"""
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "vision_epp")

def create_database():
    """Crea la base de datos si no existe"""
    try:
        # Conectar sin especificar base de datos
        connection = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Crear base de datos
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"✅ Base de datos '{DB_NAME}' creada/verificada")
            
            cursor.close()
            connection.close()
            return True
            
    except Error as e:
        print(f"❌ Error al conectar con MySQL: {e}")
        print(f"\n🔍 Verifica:")
        print(f"   - MySQL está corriendo")
        print(f"   - Usuario: {DB_USER}")
        print(f"   - Password: {'***' if DB_PASSWORD else '(vacío)'}")
        print(f"   - Host: {DB_HOST}:{DB_PORT}")
        return False

def init_tables():
    """Crea las tablas usando SQLAlchemy"""
    try:
        from backend.core.database import init_database, seed_initial_data
        
        print("\n🔧 Creando tablas...")
        init_database()
        
        print("\n📦 Insertando datos iniciales...")
        seed_initial_data()
        
        print("\n✨ Base de datos inicializada correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error creando tablas: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🗄️  INICIALIZACIÓN DE BASE DE DATOS - EPPVISION")
    print("=" * 60)
    print(f"\n📍 Configuración:")
    print(f"   Host: {DB_HOST}:{DB_PORT}")
    print(f"   Usuario: {DB_USER}")
    print(f"   Base de datos: {DB_NAME}\n")
    
    # Paso 1: Crear base de datos
    if create_database():
        # Paso 2: Crear tablas
        if init_tables():
            print("\n" + "=" * 60)
            print("✅ INICIALIZACIÓN COMPLETADA")
            print("=" * 60)
            print("\n💡 Próximos pasos:")
            print("   1. Inicia el servidor: uvicorn backend.api.main:app --reload")
            print("   2. Ve a http://localhost:8000/configuracion")
            print("   3. Agrega tus cámaras")
            print("   4. Ve a http://localhost:8000/monitoreo-vivo\n")
        else:
            print("\n❌ Falló la creación de tablas")
    else:
        print("\n❌ Falló la creación de la base de datos")

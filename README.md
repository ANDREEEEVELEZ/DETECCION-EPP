# EPPVISION - Sistema de Detección de EPP

Sistema profesional de detección automática del uso correcto, incorrecto y no uso de Equipos de Protección Personal (EPP) mediante visión computacional, desarrollado para obras de construcción en Piura 2025.

## 📋 Descripción

Este sistema utiliza tecnología de visión computacional y aprendizaje profundo (YOLOv8) para monitorear en tiempo real el cumplimiento del uso de EPP en obras de construcción, generando alertas automáticas y reportes detallados para supervisores de seguridad.

## 🎯 Características Principales

- ✅ **Monitoreo en Tiempo Real**: Stream en vivo de múltiples cámaras IP/RTSP
- ✅ **Procesamiento de Videos**: Análisis de videos pregrabados
- ✅ **Detección de 5 tipos de EPP**: Casco, Chaleco, Gafas, Guantes, Botas
- ✅ **Clasificación Inteligente**: Uso Correcto / Uso Incorrecto / No Uso
- ✅ **Alertas Automáticas**: Notificaciones en tiempo real por incumplimientos
- ✅ **Dashboard Profesional**: Métricas, gráficos y estadísticas en vivo
- ✅ **Reportes Exportables**: PDF, Excel y CSV para análisis académico
- ✅ **Interfaz Moderna**: Dark theme profesional con TailwindCSS

## 🛠️ Tecnologías Utilizadas

### Backend
- **FastAPI** - Framework web moderno y rápido
- **Python 3.10+** - Lenguaje de programación
- **YOLOv8** - Modelo de detección de objetos (próximamente)
- **Jinja2** - Motor de templates HTML

### Frontend
- **TailwindCSS** - Framework de estilos modernos
- **Alpine.js** - Interactividad ligera
- **Chart.js** - Gráficos interactivos
- **Lucide Icons** - Iconos profesionales

### Base de Datos (próximamente)
- **MySQL 8.0+** - Base de datos relacional

## 📁 Estructura del Proyecto

```
VISION_EPP/
├── backend/
│   ├── api/
│   │   ├── main.py              # Servidor FastAPI
│   │   └── routes/
│   │       └── pages.py         # Rutas de páginas
│   ├── templates/
│   │   ├── layouts/
│   │   │   └── base.html        # Layout base
│   │   ├── components/
│   │   │   ├── sidebar.html     # Navegación lateral
│   │   │   └── navbar.html      # Barra superior
│   │   └── pages/
│   │       ├── dashboard.html           # Dashboard principal
│   │       ├── monitoreo_vivo.html      # Monitoreo tiempo real
│   │       ├── historial_alertas.html   # Historial
│   │       ├── configuracion.html       # Configuración
│   │       ├── procesar_videos.html     # Subir videos
│   │       └── reportes.html            # Generar reportes
│   └── static/
│       ├── css/
│       │   └── custom.css       # Estilos personalizados
│       ├── js/
│       │   └── app.js           # JavaScript
│       └── images/
├── requirements.txt             # Dependencias Python
├── .env                        # Variables de entorno
└── README.md                   # Este archivo
```

## 🚀 Instalación

### 1. Clonar el repositorio
```bash
cd d:\VISION_EPP
```

### 2. Crear entorno virtual (recomendado)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias
```powershell
pip install -r requirements.txt
```

## ▶️ Ejecutar el Sistema

### Iniciar el servidor
```powershell
cd backend\api
python main.py
```

El sistema estará disponible en: **http://localhost:8000**

## 📱 Páginas Disponibles

- **Dashboard**: http://localhost:8000/dashboard
- **Monitoreo en Vivo**: http://localhost:8000/monitoreo-vivo
- **Historial de Alertas**: http://localhost:8000/historial-alertas
- **Configuración**: http://localhost:8000/configuracion
- **Procesar Videos**: http://localhost:8000/procesar-videos
- **Reportes**: http://localhost:8000/reportes

## 🎨 Capturas de Pantalla

### Dashboard Principal
Dashboard con métricas de cumplimiento, gráficos de tendencias y última detección de riesgo.

### Monitoreo en Tiempo Real
Stream de video en vivo con detecciones en tiempo real y panel de alertas.

### Historial de Alertas
Filtros avanzados y lista detallada de todas las alertas generadas.

### Configuración
Gestión de cámaras, parámetros del modelo IA y canales de alerta.

## 🔧 Configuración

### Variables de Entorno (.env)
```env
APP_NAME=EPPVISION
API_HOST=0.0.0.0
API_PORT=8000

EMAIL_ALERTS_ENABLED=1
SMTP_HOST=smtp.tu-servidor.com
SMTP_PORT=587
SMTP_USER=alertas@tu-dominio.com
SMTP_PASSWORD=tu_password
SMTP_FROM=alertas@tu-dominio.com
ALERT_EMAIL_TO=supervisor@tu-dominio.com,seguridad@tu-dominio.com
SMTP_USE_TLS=1
```

## 📊 Próximas Funcionalidades

- [ ] Integración con YOLOv8 para detección real
- [ ] Conexión a base de datos MySQL
- [ ] WebSockets para streaming en tiempo real
- [x] Sistema de alertas por email
- [ ] Sistema de alertas por SMS
- [ ] Exportación de reportes PDF/Excel
- [ ] Tracking multi-persona
- [ ] Estimación de pose corporal
- [ ] Clasificador C/I/N basado en ubicación de EPP

## 👨‍💻 Desarrollo

### Tecnología para Futuro Entrenamiento

El sistema está preparado para integrar:
- **YOLOv8** de Ultralytics para detección de objetos
- **OpenCV** para procesamiento de imágenes
- **PyTorch** para entrenamiento del modelo
- Dataset personalizado de EPP en obras de construcción

### Estructura de Datos

El sistema clasificará cada EPP en tres estados:
- ✅ **Uso Correcto (C)**: EPP presente y en ubicación correcta
- ⚠️ **Uso Incorrecto (I)**: EPP presente pero mal ubicado
- ❌ **No Uso (N)**: EPP completamente ausente

## 📄 Licencia

Este proyecto es parte de una tesis académica para la Universidad César Vallejo, Piura 2025.

## 📞 Contacto

**Proyecto de Tesis**: Sistema de detección del uso incorrecto de EPP mediante visión computacional en obras de Piura 2025

---

**Nota**: Esta es la versión de maquetado visual. Las funcionalidades de detección con YOLOv8 se implementarán en la siguiente fase del proyecto.

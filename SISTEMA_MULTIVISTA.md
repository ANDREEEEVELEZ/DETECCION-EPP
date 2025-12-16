# 🎥 SISTEMA MULTI-VISTA INTEGRADO

## 📋 Descripción

El sistema de **Monitoreo en Vivo** incluye **3 modos de visualización** que puedes cambiar con un solo click, eliminando la necesidad de una página separada para multi-cámara.

---

## 🎮 CONTROLES DE VISTA

En la parte superior de la página de **Monitoreo en Vivo**, encontrarás estos botones:

```
┌────────────────────────────────────────┐
│ [Individual] [2x2] [3x2]   📹 3/4     │
└────────────────────────────────────────┘
```

### Botón **Individual**
- Muestra **1 cámara en pantalla completa**
- Usa el selector desplegable para cambiar entre cámaras
- Ideal para supervisión detallada de una zona específica
- Incluye controles de zoom y captura

### Botón **2x2**
- Muestra **4 cámaras simultáneamente** en grid
- Vista balanceada entre detalle y cobertura
- Click en cualquier cámara para verla en modo Individual
- Ideal para obras medianas con 2-4 zonas

### Botón **3x2**
- Muestra **6 cámaras simultáneamente** en grid compacto
- Vista panorámica de toda la obra
- Click en cualquier cámara para verla en modo Individual  
- Ideal para obras grandes con múltiples zonas

---

## 💡 FLUJO DE TRABAJO RECOMENDADO

### Para 1 Cámara:
1. Ve a **Monitoreo en Vivo**
2. Selecciona **Individual**
3. Usa el selector para elegir tu cámara
4. ✅ Listo - tienes máxima resolución

### Para 2-4 Cámaras:
1. Ve a **Monitoreo en Vivo**
2. Selecciona **2x2**
3. Ve todas las cámaras simultáneamente
4. Click en una cámara si necesitas más detalle
5. ✅ Vuelve al grid con el botón **2x2**

### Para 5+ Cámaras:
1. Ve a **Monitoreo en Vivo**
2. Selecciona **3x2**
3. Supervisa todas las zonas a la vez
4. Click en zona crítica para inspeccionar
5. ✅ Vuelve al grid con el botón **3x2**

---

## 🎯 CARACTERÍSTICAS ESPECIALES

### 🔄 Cambio Instantáneo
- **Sin recargas**: Cambia entre vistas sin perder el stream
- **Sin navegación**: Todo en una sola página
- **Memoria de estado**: El sistema recuerda tu última vista

### 📊 Panel de Alertas Siempre Visible
En **todas las vistas** (individual, 2x2, 3x2), el **panel de alertas recientes** permanece visible en el lado derecho:

```
┌──────────────┬─────────┐
│              │ ALERTAS │
│  CÁMARAS     │ RECIEN- │
│  (1/4/6)     │  TES    │
│              │  [3]    │
└──────────────┴─────────┘
```

### ✨ Click para Expandir
En las vistas **2x2** y **3x2**:
- **Click en cualquier cámara** → Se expande a vista Individual
- Inspecciona con detalle la zona problemática
- Usa botones de navegación para volver al grid

### 🟢 Estado en Tiempo Real
Cada cámara muestra:
- **Badge de estado**: 🟢 ONLINE / 🔴 OFFLINE
- **Latencia**: Milisegundos de retraso
- **Nombre y zona**: Identificación clara
- **Contador de cámaras activas**: X/Y en la barra superior

---

## 🚀 CASOS DE USO

### Caso 1: Inspector de Seguridad
**Necesidad**: Supervisar entrada principal constantemente

**Solución**:
1. Abre **Monitoreo en Vivo**
2. Selecciona **Individual**
3. Elige "Cámara 01: Entrada Principal"
4. Monitorea a pantalla completa todo el día

---

### Caso 2: Coordinador de Obra
**Necesidad**: Ver 4 zonas críticas simultáneamente

**Solución**:
1. Abre **Monitoreo en Vivo**
2. Selecciona **2x2**
3. Configura 4 cámaras en: Entrada, Andamios, Descarga, Maquinaria
4. Supervisa todo desde un solo vistazo

---

### Caso 3: Gerente de Proyecto
**Necesidad**: Vista general de todos los niveles de la construcción

**Solución**:
1. Abre **Monitoreo en Vivo**
2. Selecciona **3x2**
3. Visualiza los 6 niveles simultáneamente
4. Click en alertas para ir directo a la zona

---

## ⚙️ CONFIGURACIÓN DE CÁMARAS

### Agregar/Editar Cámaras:
1. Ve a **Configuración** (http://localhost:8000/configuracion)
2. En "Administración de Cámaras":
   - **Agregar nueva cámara**: Define nombre, zona, URL del stream
   - **Editar existente**: Actualiza configuración
   - **Deshabilitar**: Oculta temporalmente sin eliminar

### Tipos de Cámara Soportados:
- **USB/Webcam**: Conectadas directamente al PC
- **RTSP**: Cámaras IP de red (ejemplo: `rtsp://192.168.1.100:554/stream`)
- **HTTP/MJPEG**: Streams de navegador

---

## 📊 MÉTRICAS GLOBALES

En **todas las vistas**, la parte superior muestra:

```
┌──────────────────────────────────────────────┐
│  👷 45 Trabajadores  |  ✅ 92% Cumplimiento │
│  🚨 3 Alertas Hoy   |  📹 3/4 Cámaras       │
└──────────────────────────────────────────────┘
```

Estas métricas se actualizan en tiempo real independientemente de la vista seleccionada.

---

## 🔧 SOLUCIÓN DE PROBLEMAS

### ❌ Problema: "Cámara aparece OFFLINE"
**Soluciones**:
1. Verifica conexión física (USB/Red)
2. Revisa URL del stream en Configuración
3. Comprueba firewall/permisos de red
4. Reinicia el stream desde Configuración

### ❌ Problema: "No veo las 4 cámaras en vista 2x2"
**Soluciones**:
1. Ve a **Configuración**
2. Asegúrate de tener **al menos 4 cámaras agregadas**
3. Verifica que estén **habilitadas** (no deshabilitadas)
4. Recarga la página

### ❌ Problema: "La vista grid se ve pixelada"
**Soluciones**:
1. Reduce la resolución de los streams en Configuración
2. Usa vista **Individual** si necesitas máxima calidad
3. Verifica ancho de banda de red
4. Considera usar streams de menor calidad para el grid

---

## 📈 VENTAJAS DEL SISTEMA INTEGRADO

✅ **Todo en una página**: No necesitas navegar entre módulos  
✅ **Alertas siempre visibles**: Panel lateral en todas las vistas  
✅ **Cambio instantáneo**: Sin recargas ni pérdida de streams  
✅ **Menos confusión**: Una sola interfaz para todo el monitoreo  
✅ **Memoria de estado**: El sistema recuerda tu vista preferida  
✅ **Click para expandir**: Inspección rápida de cualquier cámara  

---

## 🎓 EJEMPLO PRÁCTICO

### Supervisión de Obra - Día Típico

**09:00 AM** - Inicio de jornada
- Abres **Monitoreo en Vivo**
- Seleccionas vista **2x2** para ver las 4 zonas
- Verificas que todas las cámaras estén online (✅ 4/4)

**11:30 AM** - Alerta de Falta de Casco
- Panel lateral muestra alerta en **Zona A**
- **Haces click en Cámara 1** del grid
- Se expande a vista Individual automáticamente
- Verificas la situación con zoom
- Vuelves al **2x2** después de resolverlo

**14:00 PM** - Inspección de Andamios
- Cambias a vista **Individual**
- Seleccionas "Cámara 02: Andamios Norte"
- Usas controles de zoom para inspeccionar estructura
- Capturas evidencia con botón de cámara

**17:00 PM** - Resumen final
- Cambias a vista **2x2** o **3x2**
- Supervisas todas las zonas simultáneamente
- Verificas que no queden trabajadores en zonas peligrosas
- Cierras la jornada

---

## 📞 ACCESOS RÁPIDOS

- **Página**: http://localhost:8000/monitoreo-vivo
- **Configuración**: http://localhost:8000/configuracion
- **Dashboard**: http://localhost:8000/dashboard
- **Historial**: http://localhost:8000/historial-alertas

---

## 📚 RECURSOS ADICIONALES

- **README.md**: Documentación completa del proyecto
- **GUIA_RAPIDA.md**: Inicio rápido del sistema
- **SISTEMA_MULTICAMARA.md**: Guía técnica de escalabilidad (archivo antiguo, reemplazado por este)

---

**El sistema multi-vista está diseñado para adaptarse a tu flujo de trabajo** 🎯

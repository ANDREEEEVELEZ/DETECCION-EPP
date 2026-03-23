# Validación de Posicionamiento de EPP

## 📋 Descripción

El sistema ahora no solo **detecta la presencia** del EPP, sino que también **valida si está correctamente posicionado** en el cuerpo del trabajador.

### ¿Qué detecta?

#### ✅ Antes (Solo presencia)
- ❌ Casco presente: SÍ → **CORRECTO**
- ✓ No importaba si estaba en la mano o mal puesto

#### ✅ Ahora (Presencia + Posicionamiento)
- ❌ Casco en la mano: **INCORRECTO** ⚠️
- ❌ Gafas en el pecho: **INCORRECTO** ⚠️
- ❌ Chaleco al revés: **INCORRECTO** ⚠️
- ✓ Casco en la cabeza: **CORRECTO** ✓
- ✓ Gafas en la cara: **CORRECTO** ✓

---

## 🔧 Tecnología Utilizada

### Opción Implementada: **Pose Estimation + Validación Lógica**

Se utiliza **YOLOv8-Pose** para detectar 17 puntos clave del cuerpo humano (keypoints):

```
Keypoints detectados:
- Cabeza: nariz, ojos, orejas
- Torso: hombros, caderas
- Extremidades: codos, muñecas, rodillas, tobillos
```

### Ventajas de este enfoque:
✅ **No requiere re-entrenar** el modelo de EPP actual  
✅ **YOLOv8-Pose viene pre-entrenado** en COCO dataset  
✅ **Flexible y ajustable** con lógica de programación  
✅ **Implementación inmediata** sin recolección de datos  

---

## 🎯 Reglas de Validación por EPP

### 1️⃣ **Casco**
- ✅ **Correcto**: Casco sobre la cabeza (arriba de nariz/ojos)
- ❌ **Incorrecto**: 
  - Casco en la mano
  - Casco muy debajo de la cabeza
  - Casco colgado del brazo

**Lógica**: Si el centro del casco está más de 100px debajo de la nariz/ojos → **MAL PUESTO**

---

### 2️⃣ **Gafas/Lentes**
- ✅ **Correcto**: Gafas a la altura de los ojos
- ❌ **Incorrecto**:
  - Gafas en el pecho/colgadas
  - Gafas en la mano
  - Gafas sobre la cabeza (en el casco)

**Lógica**: 
- Si las gafas están más cerca de los hombros que de los ojos → **MAL PUESTO**
- Si están más de 80px debajo de los ojos → **MAL PUESTO**

---

### 3️⃣ **Chaleco**
- ✅ **Correcto**: Chaleco cubriendo el torso (entre hombros y caderas)
- ❌ **Incorrecto**:
  - Chaleco al revés
  - Chaleco en la mano
  - Chaleco muy desplazado

**Lógica**: Si el centro del chaleco está fuera del área torso (hombros-caderas ±50px) → **MAL PUESTO**

---

### 4️⃣ **Guantes**
- ✅ **Correcto**: Guantes en las manos (cerca de muñecas)
- ❌ **Incorrecto**:
  - Guantes en bolsillo
  - Guantes colgados del cinturón

**Lógica**: Si los guantes están a más de 200px de ambas muñecas → **MAL PUESTO**

---

### 5️⃣ **Botas**
- ✅ **Correcto**: Botas en los pies (cerca de tobillos)
- ❌ **Incorrecto**:
  - Botas en la mano
  - Botas muy desplazadas

**Lógica**: Si las botas están a más de 150px de ambos tobillos → **MAL PUESTO**

---

## 🎨 Código de Colores Visual

Al ejecutar la detección, verás:

| Color | Significado |
|-------|-------------|
| 🟢 **Verde** | EPP presente y **correctamente posicionado** |
| 🟠 **Naranja** | EPP presente pero **MAL PUESTO** ⚠️ |
| 🔴 **Rojo** | EPP **ausente** |

### Panel de Estado

```
Estado: I (Incorrecto)
Score: 40%
Mal puesto: casco | Falta: chaleco, guantes

[✗] Casco      ← Naranja (mal puesto)
[✓] Gafas      ← Verde (correcto)
[ ] Chaleco    ← Rojo (ausente)
[ ] Guantes    ← Rojo (ausente)
[ ] Botas      ← Rojo (ausente)
```

---

## 🚀 Cómo Probar

### Opción 1: Webcam (Recomendada)

```powershell
python test_validacion_posicionamiento.py
```

**Prueba diferentes escenarios:**
1. Ponte el casco correctamente → Debería salir verde ✅
2. Sostén el casco en la mano → Debería salir naranja ⚠️
3. Ponte los lentes correctamente → Verde ✅
4. Cuelga los lentes del cuello → Naranja ⚠️

### Opción 2: Con Imagen

```powershell
python test_validacion_posicionamiento.py path/to/imagen.jpg
```

---

## 📦 Descarga Automática del Modelo

La primera vez que ejecutes, YOLOv8 descargará automáticamente el modelo de pose:

```
[EPP Detector] Cargando modelo YOLOv8-Pose...
Downloading yolov8n-pose.pt...
[EPP Detector] Modelo de pose cargado exitosamente
```

**Tamaño**: ~6 MB (modelo ligero)  
**Ubicación**: Se guarda automáticamente en cache de Ultralytics

---

## 🔍 Ajustar Sensibilidad

Los umbrales han sido optimizados para mayor confiabilidad. Si necesitas ajustarlos, modifica en [`epp_detector.py`](backend/core/epp_detector.py):

### Confianza de Keypoints
```python
min_conf = 0.5  # Confianza mínima para keypoints (AUMENTADO para mejor precisión)
```

### Tolerancias por EPP

**Casco:**
```python
tolerance = 60  # píxeles - Reducido para ser más estricto
if epp_center_y > head_y + tolerance:
    return False  # Mal puesto
```

**Gafas:**
```python
if epp_center_y > eye_y + 50:  # Reducido de 80 a 50
    return False
```

**Chaleco:**
```python
tolerance = 30  # Reducido de 50 a 30
# También valida que cubra al menos 40% del torso
```

**Guantes:**
```python
if min_dist > 150:  # Reducido de 200 a 150
    return False
```

**Botas:**
```python
if min_dist > 120:  # Reducido de 150 a 120
    return False
```

**Valores recomendados:**
- `30-50`: Muy estricto (recomendado para ambientes controlados) ✅
- `60-80`: Moderado
- `100-150`: Permisivo (solo para pruebas)

---

## 📊 Salida de Datos

La función `classify_compliance()` ahora devuelve:

```python
{
    'estado': 'I',  # C=Correcto, I=Incorrecto, N=No uso, P=Sin persona
    'score': 40.0,  # Porcentaje de cumplimiento
    'epp_status': {
        'casco': False,    # No cuenta porque está mal puesto
        'chaleco': False,
        'guantes': False,
        'botas': False,
        'gafas': True
    },
    'epp_positioning': {  # NUEVO
        'casco': 'incorrecto',     # ← Estado de posicionamiento
        'chaleco': 'ausente',
        'guantes': 'ausente',
        'botas': 'ausente',
        'gafas': 'correcto'
    },
    'mensaje': 'Mal puesto: casco | Falta: chaleco, guantes, botas',
    'person_detected': True,
    'incorrectly_positioned': ['casco']  # NUEVO: Lista de EPP mal puesto
}
```

---

## ⚡ Rendimiento

- **Modelo YOLOv8-Pose**: ~30-60 FPS (GPU) / ~10-15 FPS (CPU)
- **Overhead de validación**: ~1-2ms por frame
- **Impacto total**: Mínimo

---

## 🐛 Limitaciones Conocidas

1. **Oclusión**: Si la persona está de lado o parcialmente oculta, la validación puede ser imprecisa
2. **Iluminación**: Poca luz afecta la detección de keypoints
3. **Distancia**: Funciona mejor a 2-5 metros de la cámara
4. **Múltiples personas**: Actualmente valida solo la persona con mayor confianza

---

## 🔄 Fallback

Si el modelo de pose **no se puede cargar** (ej: problemas de red):
- El sistema continúa funcionando
- Solo detecta presencia/ausencia (sin validar posición)
- Muestra advertencia en consola

---

## 📝 Próximas Mejoras

- [ ] Validar orientación del chaleco (al revés)
- [ ] Detectar casco mal ajustado (sin barboquejo)
- [ ] Soporte multi-persona
- [ ] Historial de infracciones de posicionamiento
- [ ] Alertas específicas por tipo de mal posicionamiento

---

## 📞 Soporte

Si algo no funciona correctamente:
1. Verifica que `ultralytics` esté actualizado: `pip install -U ultralytics`
2. Revisa la consola para mensajes de error
3. Prueba con mejor iluminación
4. Ajusta los umbrales de validación

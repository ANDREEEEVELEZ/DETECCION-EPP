# GUÍA RÁPIDA - EPPVISION

## 🚀 Cómo Iniciar el Sistema

### Opción 1: Usando el Script (MÁS FÁCIL)
1. Abre PowerShell en `d:\VISION_EPP`
2. Ejecuta: `.\iniciar.ps1`
3. Abre tu navegador en: http://localhost:8000

### Opción 2: Manual
1. Abre PowerShell
2. Navega a la carpeta:
   ```powershell
   cd d:\VISION_EPP\backend\api
   ```
3. Ejecuta:
   ```powershell
   python main.py
   ```
4. Abre tu navegador en: http://localhost:8000

## 📱 Páginas Disponibles

- **Dashboard**: http://localhost:8000/dashboard
- **Monitoreo en Vivo**: http://localhost:8000/monitoreo-vivo  
- **Historial de Alertas**: http://localhost:8000/historial-alertas
- **Configuración**: http://localhost:8000/configuracion
- **Procesar Videos**: http://localhost:8000/procesar-videos
- **Reportes**: http://localhost:8000/reportes

## ⚙️ Si tienes problemas

### Error: "pip no reconocido"
```powershell
python -m pip install -r requirements.txt
```

### Error: "ModuleNotFoundError: No module named 'fastapi'"
```powershell
pip install fastapi uvicorn jinja2
```

### Puerto 8000 ocupado
Edita `backend\api\main.py` y cambia el puerto:
```python
uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
```

## 🎨 Estado Actual del Sistema

✅ **Completado** (Maquetado Visual):
- Layout profesional con sidebar
- Dashboard con métricas y gráficos
- Monitoreo en vivo (placeholder)
- Historial de alertas
- Configuración del sistema
- Páginas de procesamiento y reportes

⏳ **Pendiente** (Próxima Fase):
- Integración con YOLOv8
- Detección real de EPP
- Base de datos MySQL
- WebSockets para streaming
- Sistema de alertas funcional

## 📝 Notas Importantes

- **Sin datos**: El sistema está vacío a propósito para evitar confusión con datos de prueba
- **Solo visual**: Las detecciones y alertas son placeholders
- **Listo para YOLOv8**: La estructura está preparada para integrar el modelo de IA

## 🔧 Próximos Pasos

1. Entrenar modelo YOLOv8 con dataset de EPP
2. Implementar módulos de detección en `backend/core/`
3. Conectar base de datos MySQL
4. Agregar funcionalidad real a los botones
5. Implementar WebSockets para streaming

## 📞 Ayuda

Si necesitas ayuda, revisa:
- README.md (documentación completa)
- Los comentarios en el código
- La estructura de carpetas

---

**Versión**: 1.0.0 (Maquetado Visual)  
**Fecha**: Diciembre 2025  
**Proyecto**: Tesis UCV Piura

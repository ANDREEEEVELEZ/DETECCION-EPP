"""
Rutas para procesamiento de imágenes con detección de EPP.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import cv2
import os
import sys
import uuid
from pathlib import Path
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

router = APIRouter()

ORIGINAL_IMAGE_DIR = Path("backend/static/temp_images")
ORIGINAL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

RESULT_IMAGE_DIR = Path("backend/static/processed_images")
RESULT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

epp_detector = None


def _load_detector():
    """Carga el detector EPP una sola vez para reutilizarlo en imágenes."""
    global epp_detector

    if epp_detector is not None:
        return epp_detector

    print("[IMAGES] Cargando modelo EPP para procesamiento de imágenes...")
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    sys.path.insert(0, project_root)

    from backend.core.epp_detector import EPPDetector

    model_path = os.getenv("EPP_MODEL_PATH", "models/best 22042026V1.pt")
    conf_threshold = float(os.getenv("EPP_CONF_THRESHOLD", "0.20"))
    epp_detector = EPPDetector(model_path=model_path, conf_threshold=conf_threshold)
    return epp_detector


def _encode_image(frame: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise ValueError("No se pudo codificar la imagen procesada")
    return buffer.tobytes()


@router.post("/images/process")
async def process_image(file: UploadFile = File(...)):
    """Procesa una imagen subida y devuelve el resultado con EPP anotado."""
    try:
        allowed_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Formato no soportado. Use: {', '.join(sorted(allowed_extensions))}"
            )

        image_id = str(uuid.uuid4())
        original_path = ORIGINAL_IMAGE_DIR / f"{image_id}{file_extension}"
        result_filename = f"{image_id}.jpg"
        result_path = RESULT_IMAGE_DIR / result_filename

        contents = await file.read()
        image_array = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="No se pudo leer la imagen enviada")

        with original_path.open("wb") as buffer:
            buffer.write(contents)

        detector = _load_detector()
        processed_frame, detections, compliance = detector.process_frame(frame.copy(), draw=True)

        cv2.imwrite(str(result_path), processed_frame)

        height, width = frame.shape[:2]
        result = {
            "success": True,
            "image_id": image_id,
            "filename": file.filename,
            "resolution": f"{width}x{height}",
            "detections": len(detections),
            "compliance": compliance,
            "detections_detail": detections,
            "original_image_path": f"static/temp_images/{original_path.name}",
            "processed_image_path": f"static/processed_images/{result_filename}",
        }

        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        print(f"[IMAGES ERROR] Error procesando imagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))

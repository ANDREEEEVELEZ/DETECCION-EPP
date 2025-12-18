"""
Detector de EPP usando YOLOv8
"""
import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Dict, Tuple, Optional

class EPPDetector:
    def __init__(self, model_path: str = "models/best.pt", conf_threshold: float = 0.25):
        """
        Inicializa el detector de EPP
        
        Args:
            model_path: Ruta al modelo YOLOv8 entrenado
            conf_threshold: Umbral de confianza para detecciones (0-1)
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = 0.45
        
        # Cargar modelo
        print(f"[EPP Detector] Cargando modelo desde: {model_path}")
        try:
            self.model = YOLO(model_path)
            print(f"[EPP Detector] Modelo cargado exitosamente")
            print(f"[EPP Detector] Clases del modelo: {self.model.names}")
        except Exception as e:
            print(f"[EPP Detector ERROR] No se pudo cargar el modelo: {e}")
            raise
        
        # Mapeo de clases del modelo a nombres en español
        self.class_mapping = {
            'glove': 'guantes',
            'goggles': 'gafas', 
            'helmet': 'casco',
            'hardhat': 'casco',
            'mask': 'mascarilla',
            'no_glove': 'sin_guantes',
            'no_goggles': 'sin_gafas',
            'no_helmet': 'sin_casco',
            'no_hardhat': 'sin_casco',
            'no_mask': 'sin_mascarilla',
            'no_shoes': 'sin_botas',
            'shoes': 'botas',
            'safety_vest': 'chaleco',
            'Safety Vest': 'chaleco',
            'NO-Safety Vest': 'sin_chaleco',
            'Hardhat': 'casco',
            'NO-Hardhat': 'sin_casco',
            'Gloves': 'guantes',
            'NO-Gloves': 'sin_guantes',
            'Goggles': 'gafas',
            'NO-Goggles': 'sin_gafas',
            'Mask': 'mascarilla',
            'NO-Mask': 'sin_mascarilla',
            'Person': 'persona'
        }
        
        # EPP requerido (5 tipos según la tesis)
        self.epp_types = ['casco', 'chaleco', 'guantes', 'botas', 'gafas']
        
    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        Ejecuta detección en un frame
        
        Args:
            frame: Frame de video (BGR)
            
        Returns:
            Lista de detecciones con formato:
            [
                {
                    'bbox': [x1, y1, x2, y2],
                    'confidence': float,
                    'class': str (nombre de clase),
                    'has_epp': bool (True si lleva, False si no lleva),
                    'epp_type': str (tipo de EPP: casco, chaleco, etc.)
                }
            ]
        """
        results = self.model(frame, conf=self.conf_threshold, iou=self.iou_threshold, verbose=False)
        
        detections = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Obtener datos de la caja
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                
                # Nombre de clase original del modelo
                class_name = self.model.names[cls_id]
                
                # Determinar si es EPP presente o ausente
                has_epp = not class_name.lower().startswith(('no_', 'no-'))
                
                # Mapear a nombre en español y tipo de EPP
                epp_type = self.class_mapping.get(class_name, class_name.lower())
                
                # Normalizar tipo de EPP (quitar "sin_")
                if epp_type.startswith('sin_'):
                    epp_type = epp_type.replace('sin_', '')
                
                detections.append({
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': conf,
                    'class': class_name,
                    'has_epp': has_epp,
                    'epp_type': epp_type
                })
        
        return detections
    
    def classify_compliance(self, detections: List[Dict]) -> Dict:
        """
        Clasifica el cumplimiento de EPP en: Correcto (C), Incorrecto (I), No uso (N)
        
        Args:
            detections: Lista de detecciones del método detect()
            
        Returns:
            {
                'estado': 'C' | 'I' | 'N',
                'score': float (0-100),
                'epp_status': {
                    'casco': bool,
                    'chaleco': bool,
                    'guantes': bool,
                    'botas': bool,
                    'gafas': bool
                },
                'mensaje': str
            }
        """
        # Inicializar estado de cada EPP
        epp_status = {epp: False for epp in self.epp_types}
        
        # Revisar detecciones
        for det in detections:
            epp_type = det['epp_type']
            has_epp = det['has_epp']
            
            # Solo marcar como presente si tiene EPP correcto
            if epp_type in epp_status and has_epp:
                epp_status[epp_type] = True
        
        # Contar EPP presentes
        compliant_count = sum(epp_status.values())
        total_required = len(self.epp_types)
        
        # Calcular score (0-100%)
        score = (compliant_count / total_required) * 100
        
        # Determinar estado
        if compliant_count == total_required:
            estado = 'C'  # Correcto
            mensaje = 'EPP Completo'
        elif compliant_count > 0:
            estado = 'I'  # Incorrecto (uso parcial)
            missing = [epp for epp, present in epp_status.items() if not present]
            mensaje = f'Falta: {", ".join(missing)}'
        else:
            estado = 'N'  # No uso
            mensaje = 'Sin EPP'
        
        return {
            'estado': estado,
            'score': score,
            'epp_status': epp_status,
            'mensaje': mensaje
        }
    
    def draw_detections(self, frame: np.ndarray, detections: List[Dict], compliance: Dict) -> np.ndarray:
        """
        Dibuja las detecciones y estado de cumplimiento en el frame
        
        Args:
            frame: Frame original
            detections: Detecciones del método detect()
            compliance: Clasificación del método classify_compliance()
            
        Returns:
            Frame con anotaciones dibujadas
        """
        frame_annotated = frame.copy()
        
        # Colores
        COLOR_CORRECTO = (0, 255, 0)  # Verde
        COLOR_INCORRECTO = (0, 0, 255)  # Rojo
        COLOR_ADVERTENCIA = (0, 165, 255)  # Naranja
        
        # Dibujar cada detección
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            conf = det['confidence']
            has_epp = det['has_epp']
            epp_type = det['epp_type']
            
            # Color según si tiene o no EPP
            color = COLOR_CORRECTO if has_epp else COLOR_INCORRECTO
            
            # Dibujar bounding box
            cv2.rectangle(frame_annotated, (x1, y1), (x2, y2), color, 2)
            
            # Etiqueta
            label = f"{epp_type} {conf:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            
            # Fondo de etiqueta
            cv2.rectangle(frame_annotated, 
                         (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), 
                         color, -1)
            
            # Texto de etiqueta
            cv2.putText(frame_annotated, label, 
                       (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Panel de estado en la esquina superior izquierda
        estado = compliance['estado']
        score = compliance['score']
        mensaje = compliance['mensaje']
        
        # Color del panel según estado
        if estado == 'C':
            panel_color = COLOR_CORRECTO
        elif estado == 'I':
            panel_color = COLOR_ADVERTENCIA
        else:
            panel_color = COLOR_INCORRECTO
        
        # Dibujar panel de estado
        panel_height = 120
        panel_width = 250
        overlay = frame_annotated.copy()
        cv2.rectangle(overlay, (10, 10), (panel_width, panel_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame_annotated, 0.3, 0, frame_annotated)
        
        # Texto del panel
        cv2.putText(frame_annotated, f"Estado: {estado}", 
                   (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, panel_color, 2)
        cv2.putText(frame_annotated, f"Score: {score:.0f}%", 
                   (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame_annotated, mensaje, 
                   (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Lista de EPP con checkmarks
        y_offset = 105
        for epp, present in compliance['epp_status'].items():
            symbol = "[X]" if present else "[ ]"
            color = COLOR_CORRECTO if present else COLOR_INCORRECTO
            text = f"{symbol} {epp.capitalize()}"
            # Solo mostrar primeros 3 para no saturar
            if y_offset < panel_height:
                cv2.putText(frame_annotated, text, 
                           (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
                y_offset += 20
        
        return frame_annotated
    
    def process_frame(self, frame: np.ndarray, draw: bool = True) -> Tuple[np.ndarray, List[Dict], Dict]:
        """
        Procesa un frame completo: detecta, clasifica y opcionalmente dibuja
        
        Args:
            frame: Frame de video
            draw: Si True, dibuja las detecciones en el frame
            
        Returns:
            (frame_procesado, detections, compliance)
        """
        # Detectar EPP
        detections = self.detect(frame)
        
        # Clasificar cumplimiento
        compliance = self.classify_compliance(detections)
        
        # Dibujar si se solicita
        if draw:
            frame = self.draw_detections(frame, detections, compliance)
        
        return frame, detections, compliance

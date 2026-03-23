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
        
        # Cargar modelo de detección de EPP
        print(f"[EPP Detector] Cargando modelo desde: {model_path}")
        try:
            self.model = YOLO(model_path)
            print(f"[EPP Detector] Modelo cargado exitosamente")
            print(f"[EPP Detector] Clases del modelo: {self.model.names}")
        except Exception as e:
            print(f"[EPP Detector ERROR] No se pudo cargar el modelo: {e}")
            raise
        
        # Cargar modelo de pose para validación de posicionamiento
        print(f"[EPP Detector] Cargando modelo YOLOv8-Pose...")
        try:
            self.pose_model = YOLO('yolov8n-pose.pt')  # Modelo ligero de pose
            print(f"[EPP Detector] Modelo de pose cargado exitosamente")
        except Exception as e:
            print(f"[EPP Detector WARNING] No se pudo cargar modelo de pose: {e}")
            print(f"[EPP Detector] Continuando sin validación de posicionamiento")
            self.pose_model = None
        
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
        
        # Índices de keypoints de YOLO-Pose (COCO format)
        # 0: nose, 1: left_eye, 2: right_eye, 3: left_ear, 4: right_ear,
        # 5: left_shoulder, 6: right_shoulder, 7: left_elbow, 8: right_elbow,
        # 9: left_wrist, 10: right_wrist, 11: left_hip, 12: right_hip,
        # 13: left_knee, 14: right_knee, 15: left_ankle, 16: right_ankle
        self.KEYPOINT_NAMES = {
            0: 'nose', 1: 'left_eye', 2: 'right_eye', 3: 'left_ear', 4: 'right_ear',
            5: 'left_shoulder', 6: 'right_shoulder', 7: 'left_elbow', 8: 'right_elbow',
            9: 'left_wrist', 10: 'right_wrist', 11: 'left_hip', 12: 'right_hip',
            13: 'left_knee', 14: 'right_knee', 15: 'left_ankle', 16: 'right_ankle'
        }
        
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
    
    def detect_pose_keypoints(self, frame: np.ndarray) -> Optional[Dict]:
        """
        Detecta los keypoints del cuerpo humano usando YOLOv8-Pose
        
        Args:
            frame: Frame de video (BGR)
            
        Returns:
            Dict con keypoints o None si no se detecta persona:
            {
                'keypoints': np.array (17, 3) - [x, y, confidence],
                'bbox': [x1, y1, x2, y2],
                'confidence': float
            }
        """
        if self.pose_model is None:
            return None
        
        try:
            # AUMENTAR confianza mínima para detección de pose
            results = self.pose_model(frame, conf=0.4, verbose=False)  # Aumentado de 0.3 a 0.4
            
            # Tomar la primera persona detectada con mayor confianza
            if len(results) > 0 and results[0].keypoints is not None:
                keypoints_data = results[0].keypoints.data.cpu().numpy()
                
                if len(keypoints_data) > 0:
                    # Tomar la detección con mayor confianza
                    keypoints = keypoints_data[0]  # Shape: (17, 3) - [x, y, conf]
                    
                    # Obtener bbox de la persona
                    boxes = results[0].boxes
                    if len(boxes) > 0:
                        box = boxes[0]
                        bbox = box.xyxy[0].cpu().numpy().astype(int)
                        conf = float(box.conf[0].cpu().numpy())
                    else:
                        bbox = None
                        conf = 0.0
                    
                    return {
                        'keypoints': keypoints,
                        'bbox': bbox,
                        'confidence': conf
                    }
        except Exception as e:
            print(f"[EPP Detector] Error en detección de pose: {e}")
        
        return None
    
    def _calculate_iou(self, box1: List, box2: List) -> float:
        """
        Calcula Intersection over Union entre dos bounding boxes
        """
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        # Área de intersección
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
            return 0.0
        
        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
        
        # Área de unión
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = box1_area + box2_area - inter_area
        
        if union_area == 0:
            return 0.0
        
        return inter_area / union_area
    
    def validate_epp_position(self, epp_bbox: List, epp_type: str, pose_data: Optional[Dict]) -> bool:
        """
        Valida si un EPP está correctamente posicionado en el cuerpo
        
        Args:
            epp_bbox: Bounding box del EPP [x1, y1, x2, y2]
            epp_type: Tipo de EPP ('casco', 'gafas', 'chaleco', etc.)
            pose_data: Datos de keypoints del cuerpo
            
        Returns:
            True si está bien posicionado, False si está mal puesto
        """
        # Si no tenemos datos de pose, asumir que está correcto
        if pose_data is None or pose_data['keypoints'] is None:
            return True
        
        keypoints = pose_data['keypoints']
        epp_x1, epp_y1, epp_x2, epp_y2 = epp_bbox
        epp_center_x = (epp_x1 + epp_x2) / 2
        epp_center_y = (epp_y1 + epp_y2) / 2
        
        # VALIDACIÓN POR TIPO DE EPP
        
        if epp_type == 'casco':
            # El casco debe estar SOBRE la cabeza (arriba de ojos/nariz)
            nose = keypoints[0]  # nariz
            left_eye = keypoints[1]
            right_eye = keypoints[2]
            left_ear = keypoints[3]
            right_ear = keypoints[4]
            
            # AUMENTAR confianza mínima para mejor precisión
            min_conf = 0.5
            
            # Recopilar todos los keypoints de la cabeza con buena confianza
            head_keypoints = []
            if nose[2] > min_conf:
                head_keypoints.append(nose[1])
            if left_eye[2] > min_conf:
                head_keypoints.append(left_eye[1])
            if right_eye[2] > min_conf:
                head_keypoints.append(right_eye[1])
            if left_ear[2] > min_conf:
                head_keypoints.append(left_ear[1])
            if right_ear[2] > min_conf:
                head_keypoints.append(right_ear[1])
            
            # Si no tenemos suficientes keypoints confiables, ser CONSERVADOR
            if len(head_keypoints) < 2:
                # Si no detectamos bien la cabeza, asumir INCORRECTO si está muy abajo
                # Usar cualquier keypoint disponible
                if nose[2] > 0.3:
                    head_y = nose[1]
                elif left_eye[2] > 0.3 or right_eye[2] > 0.3:
                    head_y = max(left_eye[1] if left_eye[2] > 0.3 else 9999, 
                                right_eye[1] if right_eye[2] > 0.3 else 9999)
                else:
                    return True  # No hay información, asumir correcto
                
                # Tolerancia MUY REDUCIDA cuando hay poca confianza
                if epp_center_y > head_y + 50:
                    return False
                return True
            
            # Usar el promedio de keypoints confiables
            head_y = sum(head_keypoints) / len(head_keypoints)
            
            # Validar posición con MENOR tolerancia (más estricto)
            # El casco debe estar cerca o ARRIBA de la cabeza
            tolerance = 60  # Reducido de 100 a 60 píxeles
            
            if epp_center_y > head_y + tolerance:
                return False  # Casco muy abajo (en mano, en pecho, etc.)
            
            # Validación adicional: el casco NO debe estar demasiado arriba tampoco
            if epp_center_y < head_y - 150:
                return False  # Casco en el aire? Probablemente error de detección
            
            return True
        
        elif epp_type == 'gafas':
            # Las gafas deben estar a la altura de los OJOS, no en el pecho
            nose = keypoints[0]
            left_eye = keypoints[1]
            right_eye = keypoints[2]
            left_shoulder = keypoints[5]
            right_shoulder = keypoints[6]
            
            min_conf = 0.5
            
            # Recopilar keypoints de ojos con buena confianza
            eye_keypoints = []
            if left_eye[2] > min_conf:
                eye_keypoints.append(left_eye[1])
            if right_eye[2] > min_conf:
                eye_keypoints.append(right_eye[1])
            if nose[2] > min_conf:
                eye_keypoints.append(nose[1])
            
            if len(eye_keypoints) == 0:
                # Sin información de ojos, ser conservador
                return True
            
            eye_y = sum(eye_keypoints) / len(eye_keypoints)
            
            # Calcular posición de hombros
            shoulder_keypoints = []
            if left_shoulder[2] > min_conf:
                shoulder_keypoints.append(left_shoulder[1])
            if right_shoulder[2] > min_conf:
                shoulder_keypoints.append(right_shoulder[1])
            
            if len(shoulder_keypoints) == 0:
                # Sin hombros, usar solo validación simple
                if epp_center_y > eye_y + 60:
                    return False
                return True
            
            shoulder_y = sum(shoulder_keypoints) / len(shoulder_keypoints)
            
            # Validación 1: Las gafas deben estar CERCA de los ojos
            dist_to_eyes = abs(epp_center_y - eye_y)
            dist_to_shoulders = abs(epp_center_y - shoulder_y)
            
            # Si están más cerca de los hombros que de los ojos, están mal
            if dist_to_shoulders < dist_to_eyes:
                return False  # Gafas en el pecho/colgadas
            
            # Validación 2: Tolerancia REDUCIDA - no deben estar muy abajo de los ojos
            if epp_center_y > eye_y + 50:  # Reducido de 80 a 50
                return False
            
            # Validación 3: No deben estar demasiado arriba (ej: sobre la cabeza)
            if epp_center_y < eye_y - 80:
                return False
            
            return True
        
        elif epp_type == 'chaleco':
            # El chaleco debe cubrir el torso (entre hombros y caderas)
            left_shoulder = keypoints[5]
            right_shoulder = keypoints[6]
            left_hip = keypoints[11]
            right_hip = keypoints[12]
            
            min_conf = 0.5
            
            # Recopilar keypoints de hombros
            shoulder_keypoints = []
            if left_shoulder[2] > min_conf:
                shoulder_keypoints.append(left_shoulder[1])
            if right_shoulder[2] > min_conf:
                shoulder_keypoints.append(right_shoulder[1])
            
            # Recopilar keypoints de caderas
            hip_keypoints = []
            if left_hip[2] > min_conf:
                hip_keypoints.append(left_hip[1])
            if right_hip[2] > min_conf:
                hip_keypoints.append(right_hip[1])
            
            # Necesitamos al menos un keypoint de cada zona
            if len(shoulder_keypoints) == 0 or len(hip_keypoints) == 0:
                return True  # No podemos validar
            
            torso_top = sum(shoulder_keypoints) / len(shoulder_keypoints)
            torso_bottom = sum(hip_keypoints) / len(hip_keypoints)
            
            # El chaleco debe estar mayormente dentro del área del torso
            # Tolerancia REDUCIDA
            tolerance = 30  # Reducido de 50 a 30
            
            if epp_center_y < torso_top - tolerance or epp_center_y > torso_bottom + tolerance:
                return False  # Chaleco fuera del torso
            
            # El chaleco debe tener altura mínima (cubrir el torso)
            # Si el bbox del chaleco es muy pequeño verticalmente, puede estar doblado/mal puesto
            epp_height = epp_bbox[3] - epp_bbox[1]
            torso_height = torso_bottom - torso_top
            
            # El chaleco debe cubrir al menos el 40% del torso
            if epp_height < torso_height * 0.4:
                return False
            
            return True
        
        elif epp_type == 'guantes':
            # Los guantes deben estar cerca de las manos (muñecas)
            left_wrist = keypoints[9]
            right_wrist = keypoints[10]
            
            min_conf = 0.5
            
            # Recopilar muñecas con buena confianza
            wrist_points = []
            if left_wrist[2] > min_conf:
                wrist_points.append((left_wrist[0], left_wrist[1]))
            if right_wrist[2] > min_conf:
                wrist_points.append((right_wrist[0], right_wrist[1]))
            
            if len(wrist_points) == 0:
                return True  # No podemos validar
            
            # Verificar si el EPP está cerca de alguna muñeca
            min_dist = float('inf')
            for wx, wy in wrist_points:
                dist = np.sqrt((epp_center_x - wx)**2 + (epp_center_y - wy)**2)
                min_dist = min(min_dist, dist)
            
            # REDUCIR tolerancia de distancia (más estricto)
            if min_dist > 150:  # Reducido de 200 a 150 píxeles
                return False  # Guantes muy lejos (en bolsillo, colgados)
            
            return True
        
        elif epp_type == 'botas':
            # Las botas deben estar cerca de los pies (tobillos)
            left_ankle = keypoints[15]
            right_ankle = keypoints[16]
            left_knee = keypoints[13]
            right_knee = keypoints[14]
            
            min_conf = 0.5
            
            # Recopilar tobillos con buena confianza
            ankle_points = []
            if left_ankle[2] > min_conf:
                ankle_points.append((left_ankle[0], left_ankle[1]))
            if right_ankle[2] > min_conf:
                ankle_points.append((right_ankle[0], right_ankle[1]))
            
            if len(ankle_points) == 0:
                return True  # No podemos validar
            
            # Verificar si el EPP está cerca de algún tobillo
            min_dist = float('inf')
            for ax, ay in ankle_points:
                dist = np.sqrt((epp_center_x - ax)**2 + (epp_center_y - ay)**2)
                min_dist = min(min_dist, dist)
            
            # REDUCIR tolerancia (más estricto)
            if min_dist > 120:  # Reducido de 150 a 120
                return False
            
            # Validación adicional: las botas deben estar ABAJO (no a la altura de rodillas)
            knee_y_avg = 0
            knee_count = 0
            if left_knee[2] > min_conf:
                knee_y_avg += left_knee[1]
                knee_count += 1
            if right_knee[2] > min_conf:
                knee_y_avg += right_knee[1]
                knee_count += 1
            
            if knee_count > 0:
                knee_y_avg /= knee_count
                # Las botas deben estar DEBAJO de las rodillas
                if epp_center_y < knee_y_avg:
                    return False  # Botas demasiado arriba
            
            return True
        
        # Por defecto, asumir que está correcto
        return True
    
    def classify_compliance(self, detections: List[Dict]) -> Dict:
        """
        Clasifica el cumplimiento de EPP en: Correcto (C), Incorrecto (I), No uso (N), Sin Persona (P)
        Ahora considera si el EPP está correctamente posicionado
        
        Args:
            detections: Lista de detecciones del método detect()
            
        Returns:
            {
                'estado': 'C' | 'I' | 'N' | 'P',
                'score': float (0-100),
                'epp_status': {
                    'casco': bool,
                    'chaleco': bool,
                    'guantes': bool,
                    'botas': bool,
                    'gafas': bool
                },
                'epp_positioning': {  # NUEVO: estado de posicionamiento
                    'casco': 'correcto' | 'incorrecto' | 'ausente',
                    ...
                },
                'mensaje': str,
                'person_detected': bool
            }
        """
        # PASO 1: Verificar si hay persona detectada
        person_detected = (
            any(det['epp_type'] == 'persona' for det in detections) or
            len(detections) > 0
        )
        
        # Si NO hay detecciones, retornar estado especial (no alertar)
        if not person_detected:
            return {
                'estado': 'P',  # P = Sin Persona (no alertar)
                'score': 0,
                'epp_status': {epp: False for epp in self.epp_types},
                'epp_positioning': {epp: 'ausente' for epp in self.epp_types},
                'mensaje': 'Área vacía',
                'person_detected': False
            }
        
        # PASO 2: Evaluar EPP y su posicionamiento
        epp_status = {epp: False for epp in self.epp_types}
        epp_positioning = {epp: 'ausente' for epp in self.epp_types}
        incorrectly_positioned_items = []
        
        # Revisar detecciones de EPP
        for det in detections:
            epp_type = det['epp_type']
            has_epp = det['has_epp']
            correctly_positioned = det.get('correctly_positioned', True)
            
            if epp_type in epp_status:
                if has_epp:
                    if correctly_positioned:
                        # EPP presente Y correctamente posicionado
                        epp_status[epp_type] = True
                        epp_positioning[epp_type] = 'correcto'
                    else:
                        # EPP presente pero MAL posicionado
                        epp_status[epp_type] = False  # NO cuenta como cumplimiento
                        epp_positioning[epp_type] = 'incorrecto'
                        incorrectly_positioned_items.append(epp_type)
                else:
                    # EPP ausente
                    epp_positioning[epp_type] = 'ausente'
        
        # Contar EPP presentes Y correctamente posicionados
        compliant_count = sum(epp_status.values())
        total_required = len(self.epp_types)
        
        # Calcular score (0-100%)
        score = (compliant_count / total_required) * 100
        
        # Determinar estado y mensaje
        if compliant_count == total_required:
            estado = 'C'  # Correcto
            mensaje = 'EPP Completo y Correcto'
        elif len(incorrectly_positioned_items) > 0:
            # Hay EPP mal posicionado
            estado = 'I'  # Incorrecto
            missing = [epp for epp, present in epp_status.items() if not present]
            
            if len(missing) > 0:
                mensaje = f'Mal puesto: {', '.join(incorrectly_positioned_items)} | Falta: {', '.join(missing)}'
            else:
                mensaje = f'EPP mal puesto: {', '.join(incorrectly_positioned_items)}'
        elif compliant_count > 0:
            estado = 'I'  # Incorrecto (uso parcial)
            missing = [epp for epp, present in epp_status.items() if not present]
            mensaje = f'Falta: {', '.join(missing)}'
        else:
            estado = 'N'  # No uso
            mensaje = 'Sin EPP'
        
        return {
            'estado': estado,
            'score': score,
            'epp_status': epp_status,
            'epp_positioning': epp_positioning,
            'mensaje': mensaje,
            'person_detected': True,
            'incorrectly_positioned': incorrectly_positioned_items
        }
    
    def draw_detections(self, frame: np.ndarray, detections: List[Dict], compliance: Dict, pose_data: Optional[Dict] = None) -> np.ndarray:
        """
        Dibuja las detecciones y estado de cumplimiento en el frame
        
        Args:
            frame: Frame original
            detections: Detecciones del método detect()
            compliance: Clasificación del método classify_compliance()
            pose_data: Datos de pose para visualización (opcional)
            
        Returns:
            Frame con anotaciones dibujadas
        """
        frame_annotated = frame.copy()
        
        # Colores
        COLOR_CORRECTO = (0, 255, 0)  # Verde
        COLOR_INCORRECTO = (0, 0, 255)  # Rojo
        COLOR_MAL_POSICIONADO = (0, 165, 255)  # Naranja
        COLOR_ADVERTENCIA = (0, 165, 255)  # Naranja
        
        # Dibujar cada detección
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            conf = det['confidence']
            has_epp = det['has_epp']
            epp_type = det['epp_type']
            correctly_positioned = det.get('correctly_positioned', True)
            
            # Determinar color según estado
            if has_epp and correctly_positioned:
                color = COLOR_CORRECTO  # Verde: EPP presente y bien puesto
                status_text = "OK"
            elif has_epp and not correctly_positioned:
                color = COLOR_MAL_POSICIONADO  # Naranja: EPP presente pero mal puesto
                status_text = "MAL PUESTO"
            else:
                color = COLOR_INCORRECTO  # Rojo: EPP ausente
                status_text = "FALTA"
            
            # Dibujar bounding box
            cv2.rectangle(frame_annotated, (x1, y1), (x2, y2), color, 2)
            
            # Etiqueta
            label = f"{epp_type} {conf:.2f}"
            if has_epp and not correctly_positioned:
                label = f"{epp_type} ({status_text})"
            
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
        
        # Dibujar keypoints del cuerpo (opcional, para debugging)
        # Comentar/descomentar según necesidad
        # if pose_data is not None and pose_data.get('keypoints') is not None:
        #     keypoints = pose_data['keypoints']
        #     for i, kp in enumerate(keypoints):
        #         x, y, conf = kp
        #         if conf > 0.5:
        #             cv2.circle(frame_annotated, (int(x), int(y)), 3, (255, 0, 255), -1)
        
        # Panel de estado en la esquina superior izquierda
        estado = compliance['estado']
        score = compliance['score']
        mensaje = compliance['mensaje']
        person_detected = compliance.get('person_detected', False)
        epp_positioning = compliance.get('epp_positioning', {})
        
        # Color del panel según estado
        if estado == 'P':
            panel_color = (180, 180, 180)  # Gris claro - Sin persona
        elif estado == 'C':
            panel_color = COLOR_CORRECTO  # Verde - Correcto
        elif estado == 'I':
            panel_color = COLOR_ADVERTENCIA  # Naranja - Incorrecto
        else:
            panel_color = COLOR_INCORRECTO  # Rojo - No uso
        
        # Dibujar panel de estado
        panel_height = 150
        panel_width = 280
        overlay = frame_annotated.copy()
        cv2.rectangle(overlay, (10, 10), (panel_width, panel_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame_annotated, 0.3, 0, frame_annotated)
        
        # Texto del panel
        cv2.putText(frame_annotated, f"Estado: {estado}", 
                   (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, panel_color, 2)
        cv2.putText(frame_annotated, f"Score: {score:.0f}%", 
                   (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Mensaje (puede ser largo, dividir si es necesario)
        if len(mensaje) > 30:
            # Dividir mensaje en dos líneas
            words = mensaje.split(' | ')
            if len(words) > 1:
                cv2.putText(frame_annotated, words[0], 
                           (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
                cv2.putText(frame_annotated, words[1], 
                           (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
            else:
                cv2.putText(frame_annotated, mensaje[:30], 
                           (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
                cv2.putText(frame_annotated, mensaje[30:], 
                           (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
        else:
            cv2.putText(frame_annotated, mensaje, 
                       (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Lista de EPP con checkmarks y estado de posicionamiento
        y_offset = 110
        for epp in self.epp_types[:5]:  # Mostrar los 5 tipos principales
            present = compliance['epp_status'].get(epp, False)
            positioning = epp_positioning.get(epp, 'ausente')
            
            # Símbolo y color según estado
            if positioning == 'correcto':
                symbol = "[✓]"
                color = COLOR_CORRECTO
            elif positioning == 'incorrecto':
                symbol = "[✗]"
                color = COLOR_MAL_POSICIONADO
            else:  # ausente
                symbol = "[ ]"
                color = COLOR_INCORRECTO
            
            text = f"{symbol} {epp.capitalize()}"
            
            cv2.putText(frame_annotated, text, 
                       (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
            y_offset += 18
        
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
        # Detectar keypoints del cuerpo para validación de posicionamiento
        pose_data = self.detect_pose_keypoints(frame)
        
        # Detectar EPP
        detections = self.detect(frame)
        
        # Validar posicionamiento de cada EPP detectado
        for det in detections:
            if det['has_epp']:  # Solo validar EPP que están presentes
                is_correctly_positioned = self.validate_epp_position(
                    det['bbox'], 
                    det['epp_type'], 
                    pose_data
                )
                det['correctly_positioned'] = is_correctly_positioned
            else:
                det['correctly_positioned'] = False  # Si no tiene EPP, no está bien posicionado
        
        # Clasificar cumplimiento
        compliance = self.classify_compliance(detections)
        
        # Dibujar si se solicita
        if draw:
            frame = self.draw_detections(frame, detections, compliance, pose_data)
        
        return frame, detections, compliance

"""
Script de prueba para validación de posicionamiento de EPP
"""
import cv2
import sys
import os

# Agregar el directorio backend al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from core.epp_detector import EPPDetector

def test_with_webcam():
    """
    Prueba la validación de posicionamiento usando la webcam
    """
    print("=" * 60)
    print("PRUEBA DE VALIDACIÓN DE POSICIONAMIENTO DE EPP")
    print("=" * 60)
    print("\nInstrucciones:")
    print("1. Colócate frente a la cámara")
    print("2. Prueba diferentes posiciones del EPP:")
    print("   - Casco en la cabeza (correcto) vs en la mano (incorrecto)")
    print("   - Gafas en la cara (correcto) vs en el pecho (incorrecto)")
    print("   - Chaleco puesto (correcto) vs al revés (incorrecto)")
    print("\nCódigo de colores:")
    print("  🟢 VERDE: EPP presente y correctamente posicionado")
    print("  🟠 NARANJA: EPP presente pero MAL PUESTO")
    print("  🔴 ROJO: EPP ausente")
    print("\nPresiona 'q' para salir")
    print("=" * 60)
    
    # Inicializar detector
    detector = EPPDetector(model_path='models/best 22042026V1.pt', conf_threshold=0.25)
    
    # Abrir webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("ERROR: No se pudo abrir la webcam")
        return
    
    print("\n✓ Webcam iniciada correctamente")
    print("✓ Modelo de detección de EPP cargado")
    print("✓ Modelo de pose (YOLOv8-Pose) cargado")
    print("\nProcesando frames...\n")
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: No se pudo leer el frame")
            break
        
        # Procesar frame con validación de posicionamiento
        annotated_frame, detections, compliance = detector.process_frame(frame, draw=True)
        
        # Mostrar información de posicionamiento
        frame_count += 1
        if frame_count % 30 == 0:  # Cada segundo aproximadamente
            print(f"\n--- Frame {frame_count} ---")
            print(f"Estado: {compliance['estado']} | Score: {compliance['score']:.0f}%")
            print(f"Mensaje: {compliance['mensaje']}")
            
            if 'epp_positioning' in compliance:
                print("\nEstado de posicionamiento:")
                for epp, status in compliance['epp_positioning'].items():
                    icon = "✓" if status == "correcto" else "✗" if status == "incorrecto" else "○"
                    print(f"  {icon} {epp.capitalize()}: {status}")
            
            if 'incorrectly_positioned' in compliance and len(compliance['incorrectly_positioned']) > 0:
                print(f"\n⚠️  EPP MAL PUESTO: {', '.join(compliance['incorrectly_positioned'])}")
        
        # Mostrar frame
        cv2.imshow('Validación de Posicionamiento de EPP', annotated_frame)
        
        # Salir con 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Liberar recursos
    cap.release()
    cv2.destroyAllWindows()
    print("\n✓ Prueba finalizada")

def test_with_image(image_path: str):
    """
    Prueba la validación de posicionamiento con una imagen
    """
    print("=" * 60)
    print("PRUEBA DE VALIDACIÓN CON IMAGEN")
    print("=" * 60)
    
    # Inicializar detector
    detector = EPPDetector(model_path='models/best 22042026V1.pt', conf_threshold=0.25)
    
    # Cargar imagen
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"ERROR: No se pudo cargar la imagen desde {image_path}")
        return
    
    print(f"\n✓ Imagen cargada: {image_path}")
    
    # Procesar
    annotated_frame, detections, compliance = detector.process_frame(frame, draw=True)
    
    # Mostrar resultados
    print(f"\nEstado: {compliance['estado']} | Score: {compliance['score']:.0f}%")
    print(f"Mensaje: {compliance['mensaje']}")
    
    if 'epp_positioning' in compliance:
        print("\nEstado de posicionamiento:")
        for epp, status in compliance['epp_positioning'].items():
            icon = "✓" if status == "correcto" else "✗" if status == "incorrecto" else "○"
            print(f"  {icon} {epp.capitalize()}: {status}")
    
    if 'incorrectly_positioned' in compliance and len(compliance['incorrectly_positioned']) > 0:
        print(f"\n⚠️  EPP MAL PUESTO: {', '.join(compliance['incorrectly_positioned'])}")
    
    # Mostrar imagen
    cv2.imshow('Resultado de Validación', annotated_frame)
    print("\nPresiona cualquier tecla para salir...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Modo imagen
        image_path = sys.argv[1]
        test_with_image(image_path)
    else:
        # Modo webcam
        test_with_webcam()

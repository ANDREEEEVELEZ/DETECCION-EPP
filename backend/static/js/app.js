// JavaScript personalizado (opcional)
console.log('EPPVISION - Sistema cargado');

// Función para actualizar fecha/hora en tiempo real
function actualizarReloj() {
    const ahora = new Date();
    const opciones = { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    const fechaHora = ahora.toLocaleDateString('es-ES', opciones);
    
    const elementoReloj = document.getElementById('reloj-tiempo-real');
    if (elementoReloj) {
        elementoReloj.textContent = fechaHora;
    }
}

// Actualizar cada minuto
setInterval(actualizarReloj, 60000);
actualizarReloj();

// El Vigilante - Script Anti-Bots
// Versión pública para instalar en webs

(function() {
    const API_URL = 'https://tu-servidor.onrender.com/api/verificar';
    const API_KEY = '__API_KEY_PLACEHOLDER__';
    
    // Si no hay API key, mostrar error
    if (!API_KEY || API_KEY === '__API_KEY_PLACEHOLDER__') {
        console.error('❌ El Vigilante: Necesitas una API Key. Regístrate en https://tu-servidor.onrender.com');
        return;
    }
    
    // Recolectar huella digital
    function obtenerHuella() {
        const huella = {
            userAgent: navigator.userAgent,
            webdriver: navigator.webdriver || false,
            lenguaje: navigator.language,
            resolucion: screen.width + 'x' + screen.height,
            profundidadColor: screen.colorDepth,
            tiempoZona: Intl.DateTimeFormat().resolvedOptions().timeZone,
            plataforma: navigator.platform,
            cookies: navigator.cookieEnabled,
            timestamp: Date.now(),
            idiomas: navigator.languages,
            conexion: navigator.connection ? navigator.connection.effectiveType : 'desconocido',
            memoria: navigator.deviceMemory || 'desconocida'
        };
        
        // Canvas fingerprint (opcional)
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 200;
            canvas.height = 50;
            const ctx = canvas.getContext('2d');
            ctx.textBaseline = 'top';
            ctx.font = '14px Arial';
            ctx.fillStyle = '#f60';
            ctx.fillRect(0, 0, 200, 50);
            ctx.fillStyle = '#069';
            ctx.fillText('El Vigilante', 10, 20);
            huella.canvas = canvas.toDataURL();
        } catch(e) {
            huella.canvas = 'error';
        }
        
        return huella;
    }
    
    // Verificar con el servidor
    async function verificar() {
        const huella = obtenerHuella();
        
        try {
            const respuesta = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    api_key: API_KEY,
                    huella: huella
                })
            });
            
            const resultado = await respuesta.json();
            
            if (resultado.error) {
                console.error('❌ El Vigilante:', resultado.error);
                // Modo permisivo: si hay error, dejamos pasar
                window.dispatchEvent(new CustomEvent('vigilante-error', { detail: resultado }));
                return;
            }
            
            if (resultado.es_bot) {
                console.warn('🤖 El Vigilante detectó un bot:', resultado.motivo);
                window.dispatchEvent(new CustomEvent('vigilante-bot', { detail: resultado }));
                
                // Bloquear el acceso
                bloquear(resultado.motivo);
            } else {
                console.log('✅ El Vigilante: Humano verificado (confianza:', resultado.confianza + '%)');
                window.dispatchEvent(new CustomEvent('vigilante-humano', { detail: resultado }));
                
                // Opcional: añadir un atributo al body para que el sitio lo sepa
                document.body.setAttribute('data-vigilante', 'humano');
            }
        } catch (error) {
            console.error('❌ Error conectando con El Vigilante:', error);
            // Modo permisivo: si no puede conectar, dejamos pasar
            window.dispatchEvent(new CustomEvent('vigilante-offline', { detail: error }));
        }
    }
    
    // Bloquear al bot
    function bloquear(motivo) {
        // Guardar que fue bloqueado
        document.body.setAttribute('data-vigilante', 'bloqueado');
        
        // Redirigir a página de bloqueo
        const urlBloqueo = 'https://tu-servidor.onrender.com/api/bloquear?motivo=' + encodeURIComponent(motivo);
        
        // Opción 1: Redirigir
        window.location.href = urlBloqueo;
        
        // Opción 2: Mostrar mensaje en la misma página (descomentar si prefieres)
        /*
        document.body.innerHTML = `
            <div style="position:fixed; top:0; left:0; width:100%; height:100%; background:#000; color:#fff; display:flex; align-items:center; justify-content:center; z-index:999999; font-family:monospace;">
                <div style="text-align:center; max-width:500px; padding:20px;">
                    <h1 style="color:#ff4444;">⛔ Acceso Denegado</h1>
                    <p>El Vigilante ha detectado actividad sospechosa.</p>
                    <p><strong>Motivo:</strong> ${motivo}</p>
                    <button onclick="location.reload()">Intentar de nuevo</button>
                </div>
            </div>
        `;
        */
    }
    
    // Ejecutar cuando la página esté lista
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', verificar);
    } else {
        verificar();
    }
})();

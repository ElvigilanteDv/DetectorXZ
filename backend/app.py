from flask import Flask, request, jsonify, render_template_string
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import hashlib
import time
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Control de tasa
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per minute"],
    storage_uri="memory://"
)

# Archivo para guardar datos (en producción usa PostgreSQL)
DATA_FILE = 'datos.json'

def cargar_datos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        "usuarios": {},
        "ips_bloqueadas": {},
        "estadisticas": {"total_verificaciones": 0, "bots_detectados": 0}
    }

def guardar_datos(datos):
    with open(DATA_FILE, 'w') as f:
        json.dump(datos, f, indent=2)

# Reglas anti-bots
def analizar_huella(huella, ip):
    puntaje = 0
    motivos = []
    
    # 1. Webdriver
    if huella.get('webdriver'):
        puntaje += 100
        motivos.append("⚠️ WebDriver detectado")
    
    # 2. Resolución sospechosa
    resolucion = huella.get('resolucion', '')
    if resolucion == '800x600' or resolucion == '1024x768':
        puntaje += 70
        motivos.append("📱 Resolución de headless browser")
    
    # 3. UserAgent sospechoso
    ua = huella.get('userAgent', '').lower()
    palabras_sospechosas = ['headless', 'phantom', 'selenium', 'puppeteer', 'playwright']
    for palabra in palabras_sospechosas:
        if palabra in ua:
            puntaje += 90
            motivos.append(f"🤖 UserAgent contiene '{palabra}'")
            break
    
    # 4. Sin cookies
    if not huella.get('cookies'):
        puntaje += 40
        motivos.append("🍪 Cookies deshabilitadas")
    
    # 5. Lenguaje raro
    lenguaje = huella.get('lenguaje', '')
    if lenguaje and len(lenguaje) > 10:
        puntaje += 20
        motivos.append("🌐 Lenguaje inusual")
    
    # 6. Tiempo anormal
    ahora = int(time.time() * 1000)
    diferencia = abs(ahora - huella.get('timestamp', ahora))
    if diferencia > 60000:
        puntaje += 30
        motivos.append("⏰ Inconsistencia de tiempo")
    
    return min(puntaje, 100), motivos

# HTML de bloqueo
BLOQUEO_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Acceso Denegado - El Vigilante</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            text-align: center;
            padding: 50px;
            min-height: 100vh;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: rgba(0,0,0,0.8);
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            border: 2px solid #ff4444;
            box-shadow: 0 0 30px rgba(255,0,0,0.3);
        }
        h1 { color: #ff4444; font-size: 48px; margin: 0; }
        .motivo { background: #330000; padding: 15px; border-radius: 10px; margin: 20px 0; }
        .btn { 
            background: #ff4444; 
            color: white; 
            padding: 10px 20px; 
            text-decoration: none; 
            border-radius: 5px;
            display: inline-block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>⛔ ACCESO DENEGADO</h1>
        <p>El Vigilante ha detectado actividad de bot.</p>
        <div class="motivo">
            <strong>Motivo:</strong> {motivo}
        </div>
        <a href="javascript:history.back()" class="btn">← Intentar de nuevo</a>
    </div>
</body>
</html>
"""

@app.route('/vigilante.js')
def servir_script():
    """Entrega el script que los clientes instalan en su web"""
    api_key = request.args.get('key', '')
    with open('vigilante.js', 'r') as f:
        script = f.read()
    # Inyectar la API key en el script
    script = script.replace('__API_KEY_PLACEHOLDER__', api_key)
    return script, 200, {'Content-Type': 'application/javascript'}

@app.route('/api/verificar', methods=['POST'])
@limiter.limit("50 per minute")
def verificar():
    datos = request.get_json()
    
    if not datos or 'api_key' not in datos or 'huella' not in datos:
        return jsonify({"error": "Faltan datos"}), 400
    
    api_key = datos['api_key']
    huella = datos['huella']
    ip = request.remote_addr
    
    # Cargar datos
    data = cargar_datos()
    
    # Verificar API key
    usuario = None
    for email, info in data['usuarios'].items():
        if info['api_key'] == api_key:
            usuario = info
            usuario['email'] = email
            break
    
    if not usuario:
        return jsonify({"error": "API Key inválida"}), 403
    
    # Verificar límite
    if usuario['usos'] >= usuario['limite']:
        return jsonify({
            "es_bot": True,
            "motivo": "Límite de uso excedido - Contrata más",
            "confianza": 100
        })
    
    # Verificar IP bloqueada
    if ip in data['ips_bloqueadas']:
        usuario['usos'] += 1
        guardar_datos(data)
        return jsonify({
            "es_bot": True,
            "motivo": f"IP bloqueada: {data['ips_bloqueadas'][ip]}",
            "confianza": 100
        })
    
    # Analizar huella
    puntaje, motivos = analizar_huella(huella, ip)
    es_bot = puntaje >= 60
    
    # Actualizar estadísticas
    data['estadisticas']['total_verificaciones'] += 1
    if es_bot:
        data['estadisticas']['bots_detectados'] += 1
    
    usuario['usos'] += 1
    guardar_datos(data)
    
    return jsonify({
        "es_bot": es_bot,
        "confianza": puntaje,
        "motivo": motivos[0] if motivos else "Humano verificado",
        "puntaje": puntaje,
        "usos_restantes": usuario['limite'] - usuario['usos']
    })

@app.route('/api/bloquear', methods=['POST'])
def pagina_bloqueo():
    """Devuelve la página HTML de bloqueo"""
    motivo = request.args.get('motivo', 'Comportamiento sospechoso')
    return BLOQUEO_HTML.format(motivo=motivo)

@app.route('/')
def home():
    return render_template_string(open('../web/index.html').read())

@app.route('/dashboard')
def dashboard():
    return render_template_string(open('../web/dashboard.html').read())

@app.route('/docs')
def documentacion():
    return render_template_string(open('../web/documentacion.html').read())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

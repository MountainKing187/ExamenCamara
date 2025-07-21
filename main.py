import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from bson import ObjectId
from PIL import Image
from bson.json_util import dumps
import google.generativeai as genai
import time
from flask_socketio import SocketIO, emit
import threading

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
load_dotenv()

# Configuración
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
API_BASE = '/api/sensor'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Conectar a MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['imagen_db']
registros_collection = db['registros']

# Crear carpeta de uploads si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST')
    return response


@app.route(f'{API_BASE}', methods=['POST'])
def recibir_imagen():

    # Validar que se envió un archivo
    if 'file' not in request.files:
        return jsonify({"error": "No se encontró el archivo"}), 400
    
    # Obtener archivo
    file = request.files['file']  # 'file' debe coincidir con createFormData("file", ...)
    
    # Obtener campos adicionales
    tipo_sensor = request.form.get('tipo_sensor')  # 'tipo_sensor' debe coincidir con @Part("tipo_sensor")
    ubicacion = request.form.get('ubicacion')
    
    # Validar nombre de archivo
    if file.filename == '':
        return jsonify({"error": "Nombre de archivo vacío"}), 400
    
    # Validar tipo de archivo
    if not allowed_file(file.filename):
        return jsonify({"error": "Tipo de archivo no permitido"}), 400
    
    try:
        # Crear nombre seguro para el archivo
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Guardar archivo físicamente
        file.save(filepath)
        
        # Crear documento para MongoDB
        registro = {
            "nombre_archivo": unique_filename,
            "ruta": filepath,
            "fecha": datetime.utcnow(),
            "tipo_sensor": request.form.get('tipo_sensor', 'desconocido'),
            "ubicacion": request.form.get('ubicacion', 'desconocida'),
            "procesado": False,
            "metadata": {
                "tamaño": os.path.getsize(filepath),
                "content_type": file.content_type
            }
        }
        
        # Insertar en MongoDB
        result = registros_collection.insert_one(registro)
        registro['_id'] = str(result.inserted_id)
        
        # Emitir evento de nuevo registro en tiempo real
        socketio.emit('nuevo_registro', registro, namespace='/dashboard')
        
        # Iniciar análisis en segundo plano
        threading.Thread(target=analizar_imagen, args=(str(result.inserted_id), filepath)).start()
        
        return jsonify({
            "mensaje": "Imagen recibida y guardada",
            "registro": registro
        }), 200
    
    except Exception as e:
        return jsonify({"error": f"Error en el servidor: {str(e)}"}), 500

@app.route(f'{API_BASE}/registros', methods=['GET'])
def obtener_registros():
    try:
        # Obtener parámetros de paginación
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        skip = (page - 1) * per_page
        
        # Obtener registros con paginación
        registros = list(registros_collection.find().skip(skip).limit(per_page).sort('fecha', -1))
        total = registros_collection.count_documents({})
        
        # Convertir ObjectId a string para JSON
        for registro in registros:
            registro['_id'] = str(registro['_id'])
        
        return jsonify({
            "registros": registros,
            "paginacion": {
                "pagina_actual": page,
                "por_pagina": per_page,
                "total_registros": total,
                "total_paginas": (total + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        return jsonify({"error": f"Error al obtener registros: {str(e)}"}), 500

@app.route(f'{API_BASE}/imagen/<filename>', methods=['GET'])
def servir_imagen(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/ver')
def get_insights():
    # Obtener el tiempo actual y el de hace 1 minuto
    ahora = datetime.utcnow()
    hace_un_minuto = ahora - timedelta(minutes=1)
    
    query = {
        "fecha": {
            "$gte": hace_un_minuto,
            "$lte": ahora
        }
    }

    rutas = []
    for documento in registros_collection.find(query):
        if 'ruta' in documento:
            rutas.append(documento['ruta'])

    analisis = perform_analysis(rutas)
    
    return jsonify({"insight": analisis})

def perform_analysis(rutas):
    apiKey = os.getenv("GOOGLE_API_KEY")
    genai.configure(api_key=apiKey)
    model = genai.GenerativeModel('gemini-2.5-flash')

    try:
        """Realiza el análisis de datos con Gemini"""

        # Si no hay datos nuevos, saltar el análisis
        if not rutas:
            print("No hay nuevos datos para analizar")
            return "No hay nuevos datos para analizar"

        imagenes = [Image.open(ruta) for ruta in rutas]

        prompt = f"""
        Analiza las siguientes imagenes y describe lo que tiene.
        """
        # Construir contenido correctamente: texto + imágenes individuales
        contenido = [prompt]  # Inicia con el prompt
        contenido.extend(imagenes)  # Agrega cada imagen individualmente

        response = model.generate_content(contenido)
        analisis = response.text.strip()
        
        return analisis

    except Exception as e:
        print(f"Error en el análisis: {e}")
        time.sleep(10)
        return f"Error en el análisis: {e}"

# Función para analizar la imagen en segundo plano
def analizar_imagen(registro_id, filepath):
    try:
        apiKey = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=apiKey)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        imagen = Image.open(filepath)
        prompt = "Analiza esta imagen y describe lo que ves en detalle."
        
        response = model.generate_content([prompt, imagen])
        analisis = response.text.strip()
        
        # Actualizar el registro con el análisis
        registros_collection.update_one(
            {'_id': ObjectId(registro_id)},
            {'$set': {
                'analisis': analisis,
                'procesado': True
            }}
        )
        
        # Obtener el registro actualizado
        registro_actualizado = registros_collection.find_one({'_id': ObjectId(registro_id)})
        registro_actualizado['_id'] = str(registro_actualizado['_id'])
        
        # Emitir evento de actualización
        socketio.emit('actualizacion_analisis', registro_actualizado, namespace='/dashboard')
        
    except Exception as e:
        print(f"Error en el análisis: {e}")
        # Actualizar con error
        registros_collection.update_one(
            {'_id': ObjectId(registro_id)},
            {'$set': {
                'analisis': f"Error en el análisis: {str(e)}",
                'procesado': True
            }}
        )

# Manejo de conexiones SocketIO
@socketio.on('connect', namespace='/dashboard')
def handle_connect():
    print('Cliente conectado al dashboard')
    emit('estado', {'mensaje': 'Conectado al dashboard en tiempo real'})

# Al final del archivo, modificar el main
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8081, debug=True)

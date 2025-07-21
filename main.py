import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from bson import ObjectId
from bson.json_util import dumps

app = Flask(__name__)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=True)

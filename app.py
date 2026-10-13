"""
app.py — Servidor Flask para el Sistema de Predicción de Deserción Estudiantil.

Carga los artefactos de Machine Learning (AdaBoost) al arrancar y expone
un endpoint REST para realizar predicciones en tiempo real.
"""

import os
import traceback

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from database import init_db, insertar_evaluacion

# ---------------------------------------------------------------------------
# Configuración de la aplicación Flask
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)  # Habilitar CORS para todas las rutas

# ---------------------------------------------------------------------------
# Carga de artefactos ML al inicio (una sola vez)
# ---------------------------------------------------------------------------
MODELOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'modelos')

try:
    modelo = joblib.load(os.path.join(MODELOS_DIR, 'modelo_campeon.joblib'))
    escalador = joblib.load(os.path.join(MODELOS_DIR, 'escalador.joblib'))
    columnas = joblib.load(os.path.join(MODELOS_DIR, 'columnas_requeridas.joblib'))
    print(f"✅ Modelos cargados correctamente. Columnas esperadas: {columnas}")
except FileNotFoundError as e:
    print(f"⚠️  Error al cargar modelos: {e}")
    print("   Asegúrese de que los archivos .joblib estén en la carpeta 'modelos/'")
    modelo = None
    escalador = None
    columnas = None

# ---------------------------------------------------------------------------
# Mapeo de claves JSON (snake_case) → nombres de columnas del modelo
# ---------------------------------------------------------------------------
MAPA_CAMPOS = {
    'cu_2sem_approved': 'Curricular units 2nd sem (approved)',
    'cu_1sem_approved': 'Curricular units 1st sem (approved)',
    'cu_2sem_grade': 'Curricular units 2nd sem (grade)',
    'cu_1sem_grade': 'Curricular units 1st sem (grade)',
    'admission_grade': 'Admission grade',
    'tuition_fees_up_to_date': 'Tuition fees up to date',
    'previous_qualification_grade': 'Previous qualification (grade)',
}

# Claves obligatorias en el payload JSON
CAMPOS_OBLIGATORIOS = list(MAPA_CAMPOS.keys())

# Mapeo de clases del modelo
ETIQUETAS = {0: 'Graduado', 1: 'Desertor'}

# ---------------------------------------------------------------------------
# Inicialización de la base de datos
# ---------------------------------------------------------------------------
init_db()

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------


@app.route('/')
def index():
    """Sirve la página principal del frontend (para desarrollo local)."""
    return render_template('index.html')


@app.route('/api/predecir', methods=['POST'])
def predecir():
    """
    Endpoint principal de predicción.

    Recibe un JSON con los 7 valores numéricos obligatorios (y metadatos
    opcionales del alumno), ejecuta el pipeline ML y retorna la predicción.

    Returns:
        JSON: {status, prediccion, etiqueta, probabilidad_desercion,
               probabilidad_graduacion}
    """
    # -- Verificar que los modelos están cargados --
    if modelo is None or escalador is None or columnas is None:
        return jsonify({
            'status': 'error',
            'mensaje': 'Los modelos de ML no están cargados. Verifique la carpeta modelos/.'
        }), 500

    # -- Obtener datos del request --
    datos = request.get_json(silent=True)
    if datos is None:
        return jsonify({
            'status': 'error',
            'mensaje': 'El cuerpo de la solicitud debe ser JSON válido.'
        }), 400

    # -- Validar campos obligatorios --
    campos_faltantes = [c for c in CAMPOS_OBLIGATORIOS if c not in datos]
    if campos_faltantes:
        return jsonify({
            'status': 'error',
            'mensaje': f'Campos obligatorios faltantes: {", ".join(campos_faltantes)}'
        }), 400

    # -- Validar tipos numéricos --
    valores = {}
    for campo in CAMPOS_OBLIGATORIOS:
        try:
            valores[campo] = float(datos[campo])
        except (ValueError, TypeError):
            return jsonify({
                'status': 'error',
                'mensaje': f'El campo "{campo}" debe ser un valor numérico. Recibido: {datos[campo]}'
            }), 400

    # -- Adaptador de escala: nota previa de vigesimal (0-20) a escala interna (0-200) --
    valores['previous_qualification_grade'] = valores['previous_qualification_grade'] * 10.0

    # -- Construir DataFrame en el orden exacto del modelo --
    try:
        fila = {MAPA_CAMPOS[k]: v for k, v in valores.items()}
        df = pd.DataFrame([fila], columns=list(columnas))

        # -- Escalar y predecir --
        X_escalado = escalador.transform(df)
        prediccion = int(modelo.predict(X_escalado)[0])
        probabilidades = modelo.predict_proba(X_escalado)[0]

        # Determinar índices de clase
        clases = list(modelo.classes_)
        idx_desertor = clases.index(1) if 1 in clases else 1
        idx_graduado = clases.index(0) if 0 in clases else 0

        prob_desercion = round(float(probabilidades[idx_desertor]), 4)
        prob_graduacion = round(float(probabilidades[idx_graduado]), 4)
        etiqueta = ETIQUETAS.get(prediccion, 'Desconocido')

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'mensaje': f'Error en el pipeline de predicción: {str(e)}'
        }), 500

    # -- Registrar en base de datos --
    try:
        registro = {
            'nombre_alumno': datos.get('nombre_alumno', ''),
            'codigo_alumno': datos.get('codigo_alumno', ''),
            **valores,
            'prediccion': prediccion,
            'etiqueta': etiqueta,
            'probabilidad_desercion': prob_desercion,
            'probabilidad_graduacion': prob_graduacion,
        }
        insertar_evaluacion(registro)
    except Exception as e:
        # No bloquear la respuesta si falla la auditoría
        print(f"⚠️  Error al insertar en BD: {e}")

    # -- Respuesta exitosa --
    return jsonify({
        'status': 'ok',
        'prediccion': prediccion,
        'etiqueta': etiqueta,
        'probabilidad_desercion': prob_desercion,
        'probabilidad_graduacion': prob_graduacion,
    })


# ---------------------------------------------------------------------------
# Manejo global de errores
# ---------------------------------------------------------------------------


@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'mensaje': 'Recurso no encontrado.'}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'status': 'error', 'mensaje': 'Método HTTP no permitido.'}), 405


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'status': 'error', 'mensaje': 'Error interno del servidor.'}), 500


# ---------------------------------------------------------------------------
# Punto de entrada para desarrollo local
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

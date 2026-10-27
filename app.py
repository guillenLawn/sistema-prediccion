"""
app.py — Servidor Flask para el Sistema de Predicción de Deserción Estudiantil.

Carga los artefactos de Machine Learning (Linear SVM Calibrado) al arrancar y expone
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
    print(f"[OK] Modelos cargados correctamente. Columnas esperadas: {columnas}")
except FileNotFoundError as e:
    print(f"[WARN] Error al cargar modelos: {e}")
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
    'previous_qualification_grade': 'Previous qualification (grade)',
    'age_at_enrollment': 'Age at enrollment',
}

# Claves obligatorias en el payload JSON
CAMPOS_OBLIGATORIOS = list(MAPA_CAMPOS.keys())

# Mapeo de clases del modelo
ETIQUETAS = {0: 'Graduado', 1: 'Desertor'}

# ---------------------------------------------------------------------------
# Explicabilidad: factores críticos / a favor del diagnóstico
# ---------------------------------------------------------------------------
def _plural(n, singular, plural):
    """Retorna 'n singular' o 'n plural' según corresponda."""
    n = int(n)
    return f"{n} {singular if n == 1 else plural}"


def generar_factores(v, prediccion):
    """
    Genera una explicación orientativa del diagnóstico a partir de reglas
    académicas simples sobre los datos ingresados (no usa los coeficientes
    del modelo, que pueden ser poco intuitivos por la colinealidad entre
    cursos aprobados y promedios).

    Parámetros:
        v (dict): valores numéricos del formulario (claves snake_case).
        prediccion (int): 1 = Desertor, 0 = Graduado.

    Retorna:
        dict: {'titulo': str, 'items': [{'nivel': str, 'etiqueta': str, 'texto': str}, ...]}
              nivel ∈ {'alerta', 'info', 'favorable'}
    """
    cu1 = v['cu_1sem_approved']
    cu2 = v['cu_2sem_approved']
    g1 = v['cu_1sem_grade']
    g2 = v['cu_2sem_grade']
    adm = v['admission_grade']
    edad = v['age_at_enrollment']

    # Cada riesgo: (severidad 1-3, texto). A mayor severidad, antes aparece.
    riesgos = []
    if cu2 == 0:
        riesgos.append((3, "0 cursos aprobados en el 2.do ciclo."))
    elif cu2 <= 2:
        riesgos.append((3, f"Solo {_plural(cu2, 'curso aprobado', 'cursos aprobados')} en el 2.do ciclo."))
    elif cu2 <= 3:
        riesgos.append((2, f"Pocos cursos aprobados en el 2.do ciclo ({int(cu2)})."))

    if cu1 == 0:
        riesgos.append((3, "0 cursos aprobados en el 1.er ciclo."))
    elif cu1 <= 2:
        riesgos.append((2, f"Solo {_plural(cu1, 'curso aprobado', 'cursos aprobados')} en el 1.er ciclo."))

    if cu1 - cu2 >= 3 and cu2 > 0:
        riesgos.append((2, f"Caída de cursos aprobados entre ciclos (de {int(cu1)} a {int(cu2)})."))

    if g1 > 0 and g2 > 0 and (g1 - g2) >= 2:
        riesgos.append((2, f"Descenso notable del promedio entre el 1.er y 2.do ciclo ({g1:.2f} → {g2:.2f})."))
    elif 0 < g2 < 11:
        riesgos.append((2, f"Promedio del 2.do ciclo bajo ({g2:.2f})."))

    if adm < 110:
        riesgos.append((1, f"Nota de admisión baja ({adm:.0f}/200)."))

    if edad >= 25:
        riesgos.append((1, f"Edad de ingreso elevada ({int(edad)} años): suele asociarse a mayor carga laboral o familiar."))

    # Factores a favor
    favores = []
    if cu2 >= 6:
        favores.append((3, f"{int(cu2)} cursos aprobados en el 2.do ciclo."))
    elif cu2 >= 5:
        favores.append((2, f"{int(cu2)} cursos aprobados en el 2.do ciclo."))
    if cu1 >= 5:
        favores.append((2, f"{int(cu1)} cursos aprobados en el 1.er ciclo."))
    if g2 >= 13:
        favores.append((2, f"Buen promedio en el 2.do ciclo ({g2:.2f})."))
    if g1 >= 13:
        favores.append((1, f"Buen promedio en el 1.er ciclo ({g1:.2f})."))
    if adm >= 140:
        favores.append((1, f"Nota de admisión sólida ({adm:.0f}/200)."))
    if edad <= 20:
        favores.append((1, f"Ingreso a edad típica ({int(edad)} años)."))

    riesgos.sort(key=lambda x: -x[0])
    favores.sort(key=lambda x: -x[0])

    items = []
    if prediccion == 1:
        titulo = 'Factores críticos del diagnóstico'
        etiquetas = ['Principal factor de alerta:', 'Factor secundario:', 'Otro factor:']
        for i, (_, texto) in enumerate(riesgos[:3]):
            items.append({
                'nivel': 'alerta' if i == 0 else 'info',
                'etiqueta': etiquetas[i],
                'texto': texto,
            })
        if not items:
            items.append({
                'nivel': 'info',
                'etiqueta': '',
                'texto': 'El riesgo surge de la combinación de varios indicadores; '
                         'ninguno supera por sí solo un umbral crítico.'
            })
    else:
        titulo = 'Factores a favor del pronóstico'
        for _, texto in favores[:3]:
            items.append({'nivel': 'favorable', 'etiqueta': '', 'texto': texto})
        if not items:
            items.append({
                'nivel': 'info',
                'etiqueta': '',
                'texto': 'Perfil dentro de valores promedio, sin factores destacados a favor.'
            })
        # Aspectos a vigilar aunque el pronóstico sea favorable
        for _, texto in riesgos[:2]:
            items.append({'nivel': 'info', 'etiqueta': 'A vigilar:', 'texto': texto})

    return {'titulo': titulo, 'items': items}


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
        print(f"[WARN] Error al insertar en BD: {e}")

    # -- Explicación del diagnóstico (opcional: nunca bloquea la predicción) --
    try:
        factores = generar_factores(valores, prediccion)
    except Exception as e:
        print(f"[WARN] Error al generar factores: {e}")
        factores = None

    # -- Respuesta exitosa --
    return jsonify({
        'status': 'ok',
        'prediccion': prediccion,
        'etiqueta': etiqueta,
        'probabilidad_desercion': prob_desercion,
        'probabilidad_graduacion': prob_graduacion,
        'factores': factores,
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

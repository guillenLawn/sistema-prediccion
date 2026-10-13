"""
database.py — Módulo de persistencia SQLite para auditoría de evaluaciones.

Gestiona la conexión, creación de tabla y operaciones CRUD sobre
la tabla `historial_evaluaciones` en una base de datos SQLite local.
"""

import sqlite3
import os

# Ruta absoluta de la base de datos junto al script
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')


def _get_connection():
    """Crea y retorna una conexión SQLite con row_factory para dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crea la tabla historial_evaluaciones si no existe."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial_evaluaciones (
            id                              INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora                      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

            -- Metadatos opcionales del alumno
            nombre_alumno                   TEXT    DEFAULT '',
            codigo_alumno                   TEXT    DEFAULT '',

            -- Variables de entrada (las 7 features)
            cu_2sem_approved                REAL    NOT NULL,
            cu_1sem_approved                REAL    NOT NULL,
            cu_2sem_grade                   REAL    NOT NULL,
            cu_1sem_grade                   REAL    NOT NULL,
            admission_grade                 REAL    NOT NULL,
            tuition_fees_up_to_date         REAL    NOT NULL,
            previous_qualification_grade    REAL    NOT NULL,

            -- Resultados de la predicción
            prediccion                      INTEGER NOT NULL,
            etiqueta                        TEXT    NOT NULL,
            probabilidad_desercion          REAL    NOT NULL,
            probabilidad_graduacion         REAL    NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def insertar_evaluacion(datos):
    """
    Inserta un registro de evaluación en la base de datos.

    Parámetros:
        datos (dict): Diccionario con todas las claves correspondientes
                      a las columnas de la tabla.

    Retorna:
        int: El ID del registro insertado.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO historial_evaluaciones (
            nombre_alumno, codigo_alumno,
            cu_2sem_approved, cu_1sem_approved,
            cu_2sem_grade, cu_1sem_grade,
            admission_grade, tuition_fees_up_to_date,
            previous_qualification_grade,
            prediccion, etiqueta,
            probabilidad_desercion, probabilidad_graduacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datos.get('nombre_alumno', ''),
        datos.get('codigo_alumno', ''),
        datos['cu_2sem_approved'],
        datos['cu_1sem_approved'],
        datos['cu_2sem_grade'],
        datos['cu_1sem_grade'],
        datos['admission_grade'],
        datos['tuition_fees_up_to_date'],
        datos['previous_qualification_grade'],
        datos['prediccion'],
        datos['etiqueta'],
        datos['probabilidad_desercion'],
        datos['probabilidad_graduacion']
    ))
    conn.commit()
    registro_id = cursor.lastrowid
    conn.close()
    return registro_id


def obtener_historial():
    """
    Recupera todos los registros de evaluación ordenados por fecha descendente.

    Retorna:
        list[dict]: Lista de diccionarios con los datos de cada evaluación.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM historial_evaluaciones
        ORDER BY fecha_hora DESC
    ''')
    filas = cursor.fetchall()
    conn.close()
    return [dict(fila) for fila in filas]

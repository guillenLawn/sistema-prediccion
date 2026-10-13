/**
 * app.js — Lógica del frontend para el Sistema de Predicción de Deserción UNTELS.
 */

// Detectar URL base del API (local vs producción)
const API_BASE = window.location.hostname === 'localhost' ? '' : '';

// Referencias al DOM
const formulario = document.getElementById('formulario-prediccion');
const btnEvaluar = document.getElementById('btn-evaluar');
const seccionResultado = document.getElementById('seccion-resultado');
const resultadoIcono = document.getElementById('resultado-icono');
const resultadoTitulo = document.getElementById('resultado-titulo');
const resultadoSubtitulo = document.getElementById('resultado-subtitulo');
const probDesercionTexto = document.getElementById('prob-desercion-texto');
const probGraduacionTexto = document.getElementById('prob-graduacion-texto');
const probDesercionBar = document.getElementById('prob-desercion-bar');
const probGraduacionBar = document.getElementById('prob-graduacion-bar');
const resultadoDetalles = document.getElementById('resultado-detalles');
const btnNuevaEvaluacion = document.getElementById('btn-nueva-evaluacion');
const toastError = document.getElementById('toast-error');
const toastMensaje = document.getElementById('toast-mensaje');
const toastCerrar = document.getElementById('toast-cerrar');

// IDs de los 7 campos obligatorios
const CAMPOS = [
    'cu_1sem_approved',
    'cu_2sem_approved',
    'cu_1sem_grade',
    'cu_2sem_grade',
    'admission_grade',
    'tuition_fees_up_to_date',
    'previous_qualification_grade'
];

// ---- Envío del formulario ----
formulario.addEventListener('submit', async function (e) {
    e.preventDefault();

    // Construir payload con los valores numéricos
    const datos = {
        nombre_alumno: document.getElementById('nombre_alumno').value.trim(),
        codigo_alumno: document.getElementById('codigo_alumno').value.trim()
    };

    for (const campo of CAMPOS) {
        const valor = document.getElementById(campo).value;
        if (valor === '' || valor === null) {
            mostrarToast(`Complete el campo: ${campo}`);
            return;
        }
        datos[campo] = Number(valor);
    }

    // Activar estado de carga
    btnEvaluar.classList.add('btn--loading');
    btnEvaluar.disabled = true;

    try {
        const resp = await fetch(API_BASE + '/api/predecir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const json = await resp.json();

        if (!resp.ok || json.status === 'error') {
            mostrarToast(json.mensaje || 'Error en la solicitud');
            return;
        }

        // Mostrar resultado
        mostrarResultado(json);

    } catch (err) {
        mostrarToast('Error de conexión con el servidor: ' + err.message);
    } finally {
        btnEvaluar.classList.remove('btn--loading');
        btnEvaluar.disabled = false;
    }
});

// ---- Mostrar resultado en la tarjeta ----
function mostrarResultado(data) {
    const esDesertor = data.prediccion === 1;
    const pctDesercion = Math.round(data.probabilidad_desercion * 100);
    const pctGraduacion = Math.round(data.probabilidad_graduacion * 100);

    // Ícono
    resultadoIcono.textContent = esDesertor ? '⚠️' : '✅';
    resultadoIcono.className = 'result__icon ' +
        (esDesertor ? 'result__icon--danger' : 'result__icon--success');

    // Título
    resultadoTitulo.textContent = esDesertor ? 'Riesgo Alto de Deserción' : 'Pronóstico Favorable';
    resultadoTitulo.className = 'result__title ' +
        (esDesertor ? 'result__title--danger' : 'result__title--success');

    // Subtítulo
    resultadoSubtitulo.textContent = esDesertor
        ? 'El modelo indica una alta probabilidad de que el estudiante abandone sus estudios.'
        : 'El modelo indica que el estudiante tiene buenas probabilidades de graduarse.';

    // Barras de probabilidad (animadas con un pequeño delay)
    probDesercionTexto.textContent = pctDesercion + '%';
    probGraduacionTexto.textContent = pctGraduacion + '%';
    probDesercionBar.style.width = '0%';
    probGraduacionBar.style.width = '0%';

    setTimeout(() => {
        probDesercionBar.style.width = pctDesercion + '%';
        probGraduacionBar.style.width = pctGraduacion + '%';
    }, 100);

    // Detalles
    resultadoDetalles.innerHTML =
        `<strong>Predicción numérica:</strong> ${data.prediccion}<br>` +
        `<strong>Etiqueta:</strong> ${data.etiqueta}<br>` +
        `<strong>Prob. Deserción:</strong> ${(data.probabilidad_desercion * 100).toFixed(2)}%<br>` +
        `<strong>Prob. Graduación:</strong> ${(data.probabilidad_graduacion * 100).toFixed(2)}%`;

    // Clase de borde en la tarjeta
    seccionResultado.classList.remove('hidden', 'result--danger', 'result--success');
    seccionResultado.classList.add(esDesertor ? 'result--danger' : 'result--success');

    // Scroll suave al resultado
    seccionResultado.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ---- Nueva evaluación ----
btnNuevaEvaluacion.addEventListener('click', function () {
    formulario.reset();
    seccionResultado.classList.add('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

// ---- Toast de errores ----
function mostrarToast(mensaje) {
    toastMensaje.textContent = mensaje;
    toastError.classList.remove('hidden');
    clearTimeout(mostrarToast._timer);
    mostrarToast._timer = setTimeout(() => {
        toastError.classList.add('hidden');
    }, 6000);
}

toastCerrar.addEventListener('click', function () {
    toastError.classList.add('hidden');
});

// ---- Partículas decorativas de fondo ----
(function crearParticulas() {
    const contenedor = document.getElementById('particles');
    if (!contenedor) return;
    for (let i = 0; i < 30; i++) {
        const p = document.createElement('div');
        p.classList.add('particle');
        const size = Math.random() * 4 + 2;
        p.style.width = size + 'px';
        p.style.height = size + 'px';
        p.style.left = Math.random() * 100 + '%';
        p.style.background = Math.random() > 0.5
            ? 'rgba(96, 165, 250, 0.4)'
            : 'rgba(167, 139, 250, 0.3)';
        p.style.animationDuration = (Math.random() * 15 + 10) + 's';
        p.style.animationDelay = (Math.random() * 10) + 's';
        contenedor.appendChild(p);
    }
})();

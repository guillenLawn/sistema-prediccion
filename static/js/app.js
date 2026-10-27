/**
 * app.js — Lógica del frontend para el Sistema de Predicción de Deserción Estudiantil.
 */

// Detectar URL base del API (local vs producción)
const API_BASE = window.location.hostname === 'localhost' ? '' : '';

// Referencias al DOM
const formulario = document.getElementById('formulario-prediccion');
const btnEvaluar = document.getElementById('btn-evaluar');
const seccionResultado = document.getElementById('seccion-resultado');
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
const resultadoFactores = document.getElementById('resultado-factores');
const factoresTitulo = document.getElementById('factores-titulo');
const factoresLista = document.getElementById('factores-lista');
const btnLimpiar = document.getElementById('btn-limpiar');
const btnEjemploFavorable = document.getElementById('btn-ejemplo-favorable');
const btnEjemploRiesgo = document.getElementById('btn-ejemplo-riesgo');

// IDs de los 7 campos obligatorios
const CAMPOS = [
    'cu_1sem_approved',
    'cu_2sem_approved',
    'cu_1sem_grade',
    'cu_2sem_grade',
    'admission_grade',
    'previous_qualification_grade',
    'age_at_enrollment'
];

// Nombres legibles para los mensajes de error
const NOMBRES_CAMPOS = {
    cu_1sem_approved: 'Cursos Aprobados — 1.er Ciclo',
    cu_2sem_approved: 'Cursos Aprobados — 2.do Ciclo',
    cu_1sem_grade: 'Promedio Ponderado — 1.er Ciclo',
    cu_2sem_grade: 'Promedio Ponderado — 2.do Ciclo',
    admission_grade: 'Nota de Admisión',
    previous_qualification_grade: 'Nota de Calificación Previa (Secundaria)',
    age_at_enrollment: 'Edad de Ingreso'
};

// Alumnos de ejemplo para demostraciones rápidas
const EJEMPLOS = {
    favorable: {
        cu_1sem_approved: 6,
        cu_2sem_approved: 6,
        cu_1sem_grade: 14.5,
        cu_2sem_grade: 15,
        admission_grade: 150,
        previous_qualification_grade: 15,
        age_at_enrollment: 18
    },
    riesgo: {
        cu_1sem_approved: 2,
        cu_2sem_approved: 0,
        cu_1sem_grade: 10.5,
        cu_2sem_grade: 0,
        admission_grade: 115,
        previous_qualification_grade: 12,
        age_at_enrollment: 27
    }
};

// ---- Chips de cursos aprobados (0 a 8) ----
// Cada grupo de chips escribe su valor en un <input type="hidden"> con el id
// del campo, de modo que el resto de la lógica (validación y payload) no cambia.
function seleccionarChip(grupo, valor) {
    const input = document.getElementById(grupo.dataset.target);
    const v = (valor === null || valor === undefined || valor === '') ? '' : String(valor);
    input.value = v;
    grupo.classList.remove('input-error');
    grupo.querySelectorAll('.chip').forEach(function (chip) {
        const activo = chip.dataset.value === v;
        chip.classList.toggle('is-selected', activo);
        chip.setAttribute('aria-checked', activo ? 'true' : 'false');
    });
}

document.querySelectorAll('.chip-group').forEach(function (grupo) {
    grupo.addEventListener('click', function (e) {
        const chip = e.target.closest('.chip');
        if (!chip) return;
        seleccionarChip(grupo, chip.dataset.value);
    });
});

// ---- Alumnos de ejemplo ----
function cargarEjemplo(tipo) {
    const datos = EJEMPLOS[tipo];
    if (!datos) return;

    for (const campo of CAMPOS) {
        const el = document.getElementById(campo);
        if (el.type === 'hidden') {
            const grupo = document.querySelector('.chip-group[data-target="' + campo + '"]');
            seleccionarChip(grupo, datos[campo]);
        } else {
            el.value = datos[campo];
        }
    }

    // El resultado anterior ya no corresponde a los datos cargados
    seccionResultado.classList.add('hidden');
}

btnEjemploFavorable.addEventListener('click', function () { cargarEjemplo('favorable'); });
btnEjemploRiesgo.addEventListener('click', function () { cargarEjemplo('riesgo'); });

// ---- Limpiar formulario ----
function limpiarFormulario() {
    formulario.reset();
    document.querySelectorAll('.chip-group').forEach(function (grupo) {
        seleccionarChip(grupo, '');
    });
    seccionResultado.classList.add('hidden');
    resultadoFactores.classList.add('hidden');
}

btnLimpiar.addEventListener('click', limpiarFormulario);

// ---- Envío del formulario ----
formulario.addEventListener('submit', async function (e) {
    e.preventDefault();

    // Construir payload con los valores numéricos
    const datos = {
        nombre_alumno: document.getElementById('nombre_alumno').value.trim(),
        codigo_alumno: document.getElementById('codigo_alumno').value.trim()
    };

    for (const campo of CAMPOS) {
        const elemento = document.getElementById(campo);
        const valor = elemento.value;
        if (valor === '' || valor === null) {
            // Si es un grupo de chips, resaltarlo
            const grupo = document.querySelector('.chip-group[data-target="' + campo + '"]');
            if (grupo) {
                grupo.classList.add('input-error');
            }
            mostrarToast('Complete el campo: ' + (NOMBRES_CAMPOS[campo] || campo));
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

    // Factores críticos / a favor
    mostrarFactores(data.factores);

    // Detalles
    resultadoDetalles.innerHTML =
        `<strong>Etiqueta:</strong> ${data.etiqueta}<br>` +
        `<strong>Prob. Deserción:</strong> ${(data.probabilidad_desercion * 100).toFixed(2)}%<br>` +
        `<strong>Prob. Graduación:</strong> ${(data.probabilidad_graduacion * 100).toFixed(2)}%`;

    // Clase de borde en la tarjeta
    seccionResultado.classList.remove('hidden', 'result--danger', 'result--success');
    seccionResultado.classList.add(esDesertor ? 'result--danger' : 'result--success');

    // Scroll suave al resultado
    seccionResultado.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ---- Factores críticos del diagnóstico ----
function mostrarFactores(factores) {
    factoresLista.innerHTML = '';

    if (!factores || !Array.isArray(factores.items) || factores.items.length === 0) {
        resultadoFactores.classList.add('hidden');
        return;
    }

    factoresTitulo.textContent = factores.titulo || 'Factores del diagnóstico';

    factores.items.forEach(function (item) {
        const li = document.createElement('li');
        li.className = 'factors__item factors__item--' + item.nivel;

        const texto = document.createElement('span');
        if (item.etiqueta) {
            const negrita = document.createElement('strong');
            negrita.textContent = item.etiqueta + ' ';
            texto.appendChild(negrita);
        }
        texto.appendChild(document.createTextNode(item.texto));

        li.appendChild(texto);
        factoresLista.appendChild(li);
    });

    resultadoFactores.classList.remove('hidden');
}

// ---- Nueva evaluación ----
btnNuevaEvaluacion.addEventListener('click', function () {
    limpiarFormulario();
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

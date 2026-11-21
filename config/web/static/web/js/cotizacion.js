const form = document.getElementById("quote-form");
// Tras enviar, la página nueva llega vacía desde el servidor (Post/Redirect/Get).
// Algunos navegadores igual rellenan lo escrito antes al recargar: se descarta,
// salvo cuando la página muestra errores (ahí sí hay que conservar lo escrito).
// Además, cada formulario enviado con éxito queda anotado: si el navegador vuelve a
// mostrarlo (botón «Atrás»), se pide la página de nuevo y llega vacía.
const ENVIADOS = "mtflow-solicitudes-enviadas";
function leerEnviados() {
    try { return JSON.parse(sessionStorage.getItem(ENVIADOS) || "[]"); } catch (_) { return []; }
}
function yaEnviado() {
    const envio = form.elements.namedItem("envio");
    return Boolean(envio && envio.value && leerEnviados().includes(envio.value));
}
(function () {
    const exito = document.getElementById("dialogo-exito");
    if (exito && exito.dataset.envioEnviado) {
        try { sessionStorage.setItem(ENVIADOS, JSON.stringify([...leerEnviados(), exito.dataset.envioEnviado].slice(-20))); } catch (_) { /* sin almacenamiento */ }
    }
    if (yaEnviado()) { location.replace(location.pathname); return; }
    // Al recargar, o al volver con «Atrás» después de haber enviado una solicitud en
    // esta pestaña, el navegador rellena lo escrito antes: se descarta.
    const nav = performance.getEntriesByType && performance.getEntriesByType("navigation")[0];
    const tipo = nav ? nav.type : "";
    if (document.getElementById("form-errors")) return;
    if (tipo === "reload" || (tipo === "back_forward" && leerEnviados().length)) {
        // El navegador restaura los campos al final de la carga: se limpia en «pageshow».
        window.addEventListener("pageshow", () => {
            form.reset();
            // Sin tocar la imagen: la guardada en el servidor se conserva hasta enviar o quitarla.
            form.querySelectorAll("input:not([type=file]), select, textarea").forEach((c) => c.dispatchEvent(new Event("change", { bubbles: true })));
        }, { once: true });
    }
})();
const fileInput = document.getElementById("reference");
const preview = document.getElementById("reference-preview");
const placeholder = document.getElementById("preview-placeholder");
const fileDetails = document.getElementById("file-details");
const fileError = document.getElementById("file-error");
const summary = document.getElementById("quote-summary");
const analysisPanel = document.getElementById("live-analysis");
const analysisStatus = document.getElementById("analysis-status");
const analysisResult = document.getElementById("analysis-result");
const analysisStyle = document.getElementById("analysis-style");
const analysisNote = document.getElementById("analysis-note");
const retryAnalysis = document.getElementById("retry-analysis");
// Token de la imagen ya guardada en el servidor para esta sesión (web/imagen_pendiente.py).
const pendiente = document.getElementById("imagen-pendiente");

let objectUrl = null;
let imageReady = false;
let selectionVersion = 0;
let analysisVersion = 0;
let analysisController = null;
const percentage = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 });

function clearAnalysis() {
    analysisVersion += 1;
    if (analysisController) analysisController.abort();
    analysisController = null;
    analysisPanel.removeAttribute("aria-busy");
    analysisResult.hidden = true;
    retryAnalysis.hidden = true;
    analysisStatus.textContent = "Selecciona una imagen para ver su estilo antes de enviar.";
}

async function analyzeReference() {
    clearAnalysis();
    const file = fileInput.files[0];
    if (!imageReady || !file) return;

    const currentVersion = analysisVersion;
    const currentSelection = selectionVersion;
    const controller = new AbortController();
    analysisController = controller;
    let timedOut = false;
    const timeout = window.setTimeout(() => {
        timedOut = true;
        controller.abort();
    }, 20000);
    analysisPanel.setAttribute("aria-busy", "true");
    analysisStatus.textContent = "Analizando tu imagen…";
    const payload = new FormData();
    payload.append("imagen", file);
    payload.append("analizar", "on");
    const csrf = form.elements.namedItem("csrfmiddlewaretoken").value;
    payload.append("csrfmiddlewaretoken", csrf);
    try {
        const response = await fetch(analysisPanel.dataset.url, {
            method: "POST", body: payload, credentials: "same-origin",
            headers: { "X-CSRFToken": csrf }, signal: controller.signal,
        });
        const data = await response.json();
        if (currentSelection === selectionVersion && data.pendiente && pendiente) pendiente.value = data.pendiente;
        if (currentVersion !== analysisVersion || currentSelection !== selectionVersion) return;
        if (!response.ok || data.error) throw new Error(data.error || "No pudimos analizar la imagen.");
        analysisStyle.textContent = data.nombre;
        analysisNote.textContent = data.motivo_abstencion === "fuera_distribucion"
            ? "La referencia se aleja de los ejemplos conocidos. La tatuadora revisará la imagen; puedes continuar con tu propuesta."
            : data.estilo_sugerido === "E-99"
            ? "La referencia necesita revisión profesional para definir su estilo."
            : "La sugerencia orienta a la tatuadora y no confirma una reserva ni el precio.";
        analysisResult.hidden = false;
        analysisStatus.textContent = data.simulado
            ? "Resultado simulado: el modelo real no está activo."
            : "Análisis listo. Puedes continuar completando tu propuesta.";
    } catch (error) {
        if (currentVersion !== analysisVersion || currentSelection !== selectionVersion) return;
        if (error.name === "AbortError" && !timedOut) return;
        analysisStatus.textContent = timedOut
            ? "El análisis está tardando más de lo esperado. Puedes reintentarlo."
            : (error instanceof SyntaxError || error instanceof TypeError)
                ? "No pudimos conectar con el análisis. Reintenta o envía tu propuesta para revisión."
                : error.message;
        retryAnalysis.hidden = false;
    } finally {
        window.clearTimeout(timeout);
        if (currentVersion === analysisVersion) {
            analysisPanel.removeAttribute("aria-busy");
            analysisController = null;
        }
    }
}

retryAnalysis.addEventListener("click", analyzeReference);

function clearPreview() {
    clearAnalysis();
    selectionVersion += 1;
    imageReady = false;
    preview.onload = null;
    preview.onerror = null;
    preview.hidden = true;
    preview.removeAttribute("src");

    if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
    }

    placeholder.hidden = false;
    fileDetails.hidden = true;
    document.getElementById("file-name").textContent = "";
    if (pendiente) pendiente.value = "";
}

function rejectFile(message) {
    clearPreview();
    fileInput.value = "";
    fileError.textContent = message;
}

fileInput.addEventListener("change", () => {
    summary.hidden = true;
    fileError.textContent = "";
    clearPreview();

    const file = fileInput.files[0];
    if (!file) return;

    const allowedTypes = ["image/jpeg", "image/png"];

    if (!allowedTypes.includes(file.type)) {
        rejectFile("Selecciona una imagen JPG o PNG.");
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        rejectFile("La imagen supera el límite de 10 MB.");
        return;
    }

    const currentVersion = selectionVersion;
    objectUrl = URL.createObjectURL(file);

    preview.onload = () => {
        if (currentVersion !== selectionVersion) return;

        imageReady = true;
        preview.hidden = false;
        placeholder.hidden = true;
        fileDetails.hidden = false;
        document.getElementById("file-name").textContent = file.name;
        analyzeReference();
    };

    preview.onerror = () => {
        if (currentVersion !== selectionVersion) return;
        rejectFile("No pudimos abrir esa imagen. Prueba con otro archivo.");
    };

    preview.src = objectUrl;
});

document.getElementById("remove-image").addEventListener("click", () => {
    clearPreview();
    fileInput.value = "";
    fileError.textContent = "";
    summary.hidden = true;
});

// Oculta el resumen cuando se editan datos para evitar mostrar datos antiguos.
form.addEventListener("input", () => {
    summary.hidden = true;
});

// Tras un envío con errores, la imagen ya guardada se muestra y se reutiliza.
if (pendiente && pendiente.value && preview.getAttribute("src") && !preview.hidden) {
    imageReady = true;
    analysisStatus.textContent = "Tu imagen sigue guardada. Puedes cambiarla o quitarla; se analizará al enviar.";
}

const submitButton = document.getElementById("estimate-button");
const submitStatus = document.getElementById("submit-status");
form.addEventListener("change", () => { summary.hidden = true; });
form.addEventListener("submit", (event) => {
    if (!imageReady) {
        event.preventDefault();
        fileError.textContent = "Selecciona una imagen y espera a que cargue correctamente.";
        fileInput.focus();
        return;
    }
    if (form.dataset.submitting === "true") {
        event.preventDefault();
        return;
    }
    form.dataset.submitting = "true";
    // La recepción vuelve a clasificar en el servidor: nunca confía en datos
    // de la vista previa. Cancelar su respuesta evita mostrar un resultado viejo.
    clearAnalysis();
    submitButton.disabled = true;
    form.setAttribute("aria-busy", "true");
    submitStatus.textContent = "Guardando tu propuesta. El análisis automático de la imagen puede tardar unos segundos…";
});
window.addEventListener("pageshow", (evento) => {
    // Volver con «Atrás» después de enviar: el navegador mostraría el formulario
    // lleno desde su caché. Se pide la página de nuevo, que llega vacía.
    if (evento.persisted && yaEnviado()) { location.replace(location.pathname); return; }
    delete form.dataset.submitting;
    submitButton.disabled = false;
    form.removeAttribute("aria-busy");
    submitStatus.textContent = "";
    if (fileInput.files.length) fileInput.dispatchEvent(new Event("change"));
});
const errors = document.getElementById("form-errors");
if (errors) errors.focus();
else if (!summary.hidden) document.getElementById("summary-heading").focus();

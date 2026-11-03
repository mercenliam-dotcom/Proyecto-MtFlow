const form = document.getElementById("quote-form");
const fileInput = document.getElementById("reference");
const preview = document.getElementById("reference-preview");
const placeholder = document.getElementById("preview-placeholder");
const fileDetails = document.getElementById("file-details");
const fileError = document.getElementById("file-error");
const summary = document.getElementById("quote-summary");

let objectUrl = null;
let imageReady = false;
let selectionVersion = 0;

function clearPreview() {
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

    if (file.size > 5 * 1024 * 1024) {
        rejectFile("La imagen supera el límite de 5 MB.");
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
    submitButton.disabled = true;
    form.setAttribute("aria-busy", "true");
    submitStatus.textContent = "Preparando tu estimación. El análisis de la imagen puede tardar unos segundos…";
});
window.addEventListener("pageshow", () => {
    delete form.dataset.submitting;
    submitButton.disabled = false;
    form.removeAttribute("aria-busy");
    submitStatus.textContent = "";
    if (fileInput.files.length) fileInput.dispatchEvent(new Event("change"));
});
const errors = document.getElementById("form-errors");
if (errors) errors.focus();
else if (!summary.hidden) document.getElementById("summary-heading").focus();

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

form.addEventListener("submit", (event) => {
    event.preventDefault();

    if (!imageReady) {
        fileError.textContent = "Espera a que la imagen cargue correctamente.";
        fileInput.focus();
        return;
    }

    const value = (id) => document.getElementById(id).value.trim();

    if (!value("client-name") || !value("idea")) {
        fileError.textContent = "Completa el nombre y la descripción de tu idea.";
        return;
    }

    fileError.textContent = "";

    // textContent evita interpretar los datos ingresados como código HTML.
    document.getElementById("review-name").textContent = value("client-name");
    document.getElementById("review-email").textContent = value("client-email");
    document.getElementById("review-phone").textContent =
        value("client-phone") || "No indicado";
    document.getElementById("review-artist").textContent = value("quote-artist");
    document.getElementById("review-placement").textContent =
        `${value("body-zone")} · ${value("tattoo-size")}`;
    document.getElementById("review-idea").textContent = value("idea");

    summary.hidden = false;
    document.getElementById("summary-heading").focus();
});

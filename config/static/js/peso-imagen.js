"use strict";

// Comprobar el peso antes de abrir vistas previas o enviar el formulario.
document.querySelectorAll('input[type="file"][data-max-bytes]').forEach((input) => {
  const maximo = Number(input.dataset.maxBytes);
  const mb = (bytes) => (bytes / (1024 * 1024)).toLocaleString("es-CL", { maximumFractionDigits: 2 });
  const estado = document.createElement("small");
  estado.id = `${input.id}-peso`;
  estado.className = "ayuda";
  estado.setAttribute("aria-live", "polite");
  const error = document.createElement("div");
  error.id = `${input.id}-peso-error`;
  error.className = "error";
  error.setAttribute("role", "alert");
  input.after(estado, error);
  input.setAttribute("aria-describedby", [input.getAttribute("aria-describedby"), estado.id, error.id].filter(Boolean).join(" "));

  function validar() {
    const archivo = input.files[0];
    let mensaje = "";
    if (archivo && archivo.size === 0) mensaje = "El archivo está vacío. Selecciona otra imagen.";
    else if (archivo && archivo.size > maximo) mensaje = `La imagen pesa ${mb(archivo.size)} MB y supera el máximo de ${mb(maximo)} MB. Selecciona una más liviana.`;
    input.setCustomValidity(mensaje);
    input.setAttribute("aria-invalid", mensaje ? "true" : "false");
    error.textContent = mensaje;
    error.hidden = !mensaje;
    estado.textContent = archivo ? `Peso: ${mb(archivo.size)} MB · Máximo: ${mb(maximo)} MB.` : `Máximo: ${mb(maximo)} MB.`;
    return !mensaje;
  }

  input.addEventListener("change", validar);
  input.addEventListener("input", validar);
  // También funciona en las pantallas que usan novalidate para mostrar sus
  // otros errores en el servidor. Los archivos grandes no se envían.
  input.form.addEventListener("submit", (event) => {
    if (!validar()) {
      event.preventDefault();
      event.stopImmediatePropagation();
      input.focus();
      input.reportValidity();
    }
  }, true);
  validar();
});

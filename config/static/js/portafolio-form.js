"use strict";
/* Vista previa de la fotografía y estado de publicación en vivo. No cambia el envío. */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("portafolio-form");
  if (!form) return;
  const archivo = form.querySelector('input[type="file"]');
  const preview = document.getElementById("portafolio-preview");
  const vacio = document.getElementById("portafolio-vacio");
  const visible = document.getElementById("id_visible");
  const autorizacion = document.getElementById("id_autorizacion_publicacion");
  const carrusel = document.getElementById("id_en_carrusel");
  const estado = document.getElementById("estado-publicacion");
  let url = null;
  if (archivo) archivo.addEventListener("change", () => {
    if (url) URL.revokeObjectURL(url);
    const f = archivo.files[0];
    if (!f || !archivo.checkValidity() || !["image/jpeg", "image/png"].includes(f.type)) return;
    url = URL.createObjectURL(f);
    preview.src = url; preview.hidden = false;
    if (vacio) vacio.hidden = true;
  });
  function actualizar() {
    const publica = visible.checked && autorizacion.checked;
    estado.className = "estado-publicacion " + (publica ? "es-publica" : visible.checked ? "falta-autorizacion" : "es-borrador");
    estado.textContent = publica
      ? (carrusel.checked ? "Se verá en la página pública y en el carrusel." : "Se verá en la página pública.")
      : visible.checked ? "Falta marcar la autorización: todavía no se mostrará al público." : "Quedará como borrador privado.";
  }
  [visible, autorizacion, carrusel].forEach((c) => c && c.addEventListener("change", actualizar));
  actualizar();
});

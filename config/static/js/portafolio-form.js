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
  const vista = document.getElementById("portafolio-vista");
  const conteo = document.getElementById("portafolio-conteo");
  let urls = [];
  if (archivo) archivo.addEventListener("change", () => {
    urls.forEach((u) => URL.revokeObjectURL(u)); urls = [];
    if (url) URL.revokeObjectURL(url);
    vista.querySelectorAll(".portafolio-miniaturas").forEach((n) => n.remove());
    vista.classList.remove("con-varias");
    const validas = [...archivo.files].filter((f) => ["image/jpeg", "image/png"].includes(f.type));
    if (conteo) {
      conteo.hidden = archivo.files.length < 2;
      conteo.textContent = archivo.files.length + " fotografías seleccionadas" + (archivo.files.length > 10 ? " · el máximo por envío es 10." : ".");
      conteo.classList.toggle("conteo-excedido", archivo.files.length > 10);
    }
    if (!validas.length) return;
    if (validas.length === 1) {
      url = URL.createObjectURL(validas[0]);
      preview.src = url; preview.hidden = false;
      if (vacio) vacio.hidden = true;
      return;
    }
    // Varias: cuadrícula de miniaturas
    preview.hidden = true;
    if (vacio) vacio.hidden = true;
    const rejilla = document.createElement("div");
    rejilla.className = "portafolio-miniaturas";
    validas.slice(0, 10).forEach((f) => {
      const u = URL.createObjectURL(f); urls.push(u);
      const img = document.createElement("img");
      img.src = u; img.alt = f.name;
      rejilla.append(img);
    });
    vista.classList.add("con-varias");
    vista.append(rejilla);
  });
  // Más de 10 archivos: no enviar (el servidor lo rechazaría) y avisar.
  form.addEventListener("submit", (e) => {
    if (archivo && archivo.files.length > 10) {
      e.preventDefault();
      if (conteo) { conteo.hidden = false; conteo.classList.add("conteo-excedido"); conteo.textContent = archivo.files.length + " fotografías seleccionadas: el máximo por envío es 10. Quita algunas."; conteo.scrollIntoView({block: "center"}); }
      if (window.MTFlowAvisos) window.MTFlowAvisos.mostrar("Puedes subir hasta 10 fotografías a la vez.", "error");
    }
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

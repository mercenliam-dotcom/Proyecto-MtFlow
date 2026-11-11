"use strict";
/* Foto de perfil: muestra la vista previa y la guarda apenas se elige el archivo. */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("perfil-foto-form");
  const archivo = document.getElementById("perfil-foto-archivo");
  if (!form || !archivo) return;
  form.classList.add("con-js");  // oculta el botón «Guardar foto»: el envío es automático
  archivo.addEventListener("change", () => {
    const f = archivo.files[0];
    if (!f) return;
    if (!["image/jpeg", "image/png"].includes(f.type)) {
      if (window.MTFlowAvisos) window.MTFlowAvisos.mostrar("Solo se aceptan imágenes JPG o PNG.", "error");
      archivo.value = "";
      return;
    }
    const vista = document.getElementById("perfil-avatar-vista");
    const iniciales = document.getElementById("perfil-avatar-iniciales");
    if (vista) { vista.src = URL.createObjectURL(f); vista.hidden = false; }
    if (iniciales) iniciales.hidden = true;
    form.classList.add("subiendo");
    form.submit();
  });
});

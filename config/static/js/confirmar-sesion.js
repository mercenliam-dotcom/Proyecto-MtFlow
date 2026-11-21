"use strict";
/* Pide confirmar antes de cerrar una sesión cuyo horario aún no termina.
   Usa un diálogo propio en español: el confirm() del navegador muestra su título
   («127.0.0.1 dice…») y sus botones en el idioma del navegador. */
document.addEventListener("DOMContentLoaded", () => {
  let dialogo = null;
  function crearDialogo() {
    dialogo = document.createElement("dialog");
    dialogo.className = "dialogo-cierre";
    dialogo.setAttribute("aria-labelledby", "confirmar-sesion-titulo");
    dialogo.innerHTML = '<form method="dialog"><p class="eyebrow">ANTES DE CONTINUAR</p>' +
      '<h2 id="confirmar-sesion-titulo">La sesión aún no termina según la agenda</h2><p id="confirmar-sesion-texto"></p>' +
      '<div class="acciones"><button class="boton" value="si">Sí, continuar</button>' +
      '<button class="boton secundario" value="no">Cancelar</button></div></form>';
    document.body.append(dialogo);
    dialogo.addEventListener("click", (e) => { if (e.target === dialogo) dialogo.close("no"); });
  }
  document.querySelectorAll("button[data-confirmar-antes-de]").forEach((boton) => {
    boton.addEventListener("click", (evento) => {
      if (boton.dataset.confirmado === "1") { delete boton.dataset.confirmado; return; }
      const fin = new Date(boton.dataset.confirmarAntesDe);
      if (Number.isNaN(fin.getTime()) || new Date() >= fin) return;
      evento.preventDefault();
      if (!dialogo) crearDialogo();
      const accion = boton.value === "inasistencia" ? "registrar la inasistencia" : "marcar la sesión como realizada";
      dialogo.querySelector("#confirmar-sesion-texto").textContent = `¿Quieres ${accion} de todas formas?`;
      dialogo.returnValue = "";
      dialogo.addEventListener("close", () => {
        if (dialogo.returnValue === "si") { boton.dataset.confirmado = "1"; boton.click(); }
      }, { once: true });
      dialogo.showModal();
    });
  });
});

"use strict";
/* Pide confirmar antes de cerrar una sesión cuyo horario aún no termina.
   Reemplaza el onclick en línea, que la política de seguridad (CSP) bloqueaba. */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("button[data-confirmar-antes-de]").forEach((boton) => {
    boton.addEventListener("click", (evento) => {
      const fin = new Date(boton.dataset.confirmarAntesDe);
      if (Number.isNaN(fin.getTime()) || new Date() >= fin) return;
      const accion = boton.value === "inasistencia" ? "registrar la inasistencia" : "marcar la sesión como realizada";
      if (!window.confirm("La sesión aún no termina según la agenda. ¿Quieres " + accion + " de todas formas?")) {
        evento.preventDefault();
      }
    });
  });
});

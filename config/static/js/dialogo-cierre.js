"use strict";
// Pregunta «¿terminar ahora o continuar después?» al cerrar un trabajo.
// Sin JavaScript, los enlaces llevan a la página «Terminar trabajo».
document.addEventListener("DOMContentLoaded", () => {
    const dialogo = document.getElementById("dialogo-cierre");
    if (!dialogo || typeof dialogo.showModal !== "function") return;
    document.querySelectorAll("[data-abrir-dialogo='dialogo-cierre']").forEach(enlace => {
        enlace.addEventListener("click", evento => { evento.preventDefault(); dialogo.showModal(); });
    });
    if (dialogo.hasAttribute("data-abrir-al-cargar")) {
        dialogo.showModal();
        // Quita ?cerrar=1 para que al recargar no vuelva a aparecer.
        history.replaceState(null, "", location.pathname);
    }
    // Clic fuera del recuadro = continuar después.
    dialogo.addEventListener("click", evento => { if (evento.target === dialogo) dialogo.close(); });
});

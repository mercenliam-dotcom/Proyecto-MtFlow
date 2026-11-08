"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const dialogo = document.getElementById("decision-solicitud");
    const abrir = document.getElementById("abrir-decision");
    if (!dialogo || !abrir || typeof dialogo.showModal !== "function") return;
    abrir.hidden = false;
    abrir.addEventListener("click", () => dialogo.showModal());
    document.getElementById("cerrar-decision").addEventListener("click", () => dialogo.close());
    dialogo.addEventListener("close", () => abrir.focus());
    if (new URLSearchParams(window.location.search).get("guiado") === "1") dialogo.showModal();
});

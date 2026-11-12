"use strict";
// Los indicadores suben contando al cargar la página (CountUp.js, en static/vendor/countup).
// Solo la primera carga: la recarga automática de Métricas muestra el número directo.
document.addEventListener("DOMContentLoaded", () => {
    if (!window.countUp || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    document.querySelectorAll("[data-contar]").forEach(el => {
        const fin = Number(el.dataset.contar);
        if (!Number.isFinite(fin) || fin === 0) return;
        const contador = new countUp.CountUp(el, fin, {
            duration: fin > 999 ? 1.4 : 0.9,
            separator: el.hasAttribute("data-miles") ? "." : "",
            decimal: ",", useEasing: true,
        });
        if (!contador.error) contador.start();
    });
});

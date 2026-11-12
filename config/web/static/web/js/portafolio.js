"use strict";
const filters = document.querySelectorAll("[data-filter]");
const cards = document.querySelectorAll(".portfolio-card[data-style]");

function filtrarPorEstilo(estiloSeleccionado) {
    // 1. Estado visual de los botones superiores
    filters.forEach((filter) => {
        const active = filter.dataset.filter === estiloSeleccionado;
        filter.classList.toggle("active", active);
        filter.setAttribute("aria-pressed", String(active));
    });
    // 2. «hidden» oculta la tarjeta y la saca también del zoom a pantalla completa
    cards.forEach((card) => {
        card.hidden = !(estiloSeleccionado === "Todos" || card.dataset.style === estiloSeleccionado);
    });
}

filters.forEach((button) => {
    button.addEventListener("click", () => filtrarPorEstilo(button.dataset.filter));
});

// La etiqueta de estilo de cada tarjeta filtra; la foto abre el zoom.
document.querySelectorAll("[data-filtrar]").forEach((etiqueta) => {
    etiqueta.addEventListener("click", () => filtrarPorEstilo(etiqueta.dataset.filtrar));
});

const filters = document.querySelectorAll("[data-filter]");
const cards = document.querySelectorAll("[data-style]");

function filtrarPorEstilo(estiloSeleccionado) {
    // 1. Actualizar estado visual de los botones superiores
    filters.forEach((filter) => {
        const active = filter.dataset.filter === estiloSeleccionado;
        filter.classList.toggle("active", active);
        filter.setAttribute("aria-pressed", String(active));
    });

    // 2. Filtrar las tarjetas usando style.display para forzar la ocultación
    cards.forEach((card) => {
        const coincide = estiloSeleccionado === "Todos" || card.dataset.style === estiloSeleccionado;
        card.style.display = coincide ? "" : "none";
    });
}

// Evento para los botones superiores
filters.forEach((button) => {
    button.addEventListener("click", () => filtrarPorEstilo(button.dataset.filter));
});

// Evento para que cada tarjeta actúe como botón de filtro
cards.forEach((card) => {
    card.style.cursor = "pointer";
    card.addEventListener("click", () => filtrarPorEstilo(card.dataset.style));
});
const filters = document.querySelectorAll("[data-filter]");
const cards = document.querySelectorAll("[data-style]");

filters.forEach((button) => {
    button.addEventListener("click", () => {
        const selected = button.dataset.filter;

        filters.forEach((filter) => {
            const active = filter === button;
            filter.classList.toggle("active", active);
            filter.setAttribute("aria-pressed", String(active));
        });

        cards.forEach((card) => {
            card.hidden = selected !== "Todos"
                && card.dataset.style !== selected;
        });
    });
});

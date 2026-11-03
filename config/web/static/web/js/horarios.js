const artist = document.getElementById("artist");
const date = document.getElementById("date");
const slotsContainer = document.getElementById("time-slots");
const clearButton = document.getElementById("clear-selection");

// Datos ficticios. Más adelante se reemplazarán por disponibilidad real.
const demoSchedules = {
    "1": {
        morning: ["10:00", "10:30", "11:00", "11:30", "12:00", "12:30"],
        afternoon: ["15:00", "15:30", "16:00", "16:30", "17:00", "17:30"],
        busy: ["11:00", "16:00", "17:30"]
    },
    "2": {
        morning: ["11:00", "11:30", "12:00", "12:30"],
        afternoon: ["15:00", "15:30", "16:00", "16:30", "17:00", "17:30"],
        busy: ["12:00", "15:30", "16:30"]
    }
};

const todayParts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Santiago",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
}).formatToParts(new Date());

const part = (type) => todayParts.find((item) => item.type === type).value;
const today = `${part("year")}-${part("month")}-${part("day")}`;

date.min = today;
date.value = today;

function formatDate(value) {
    return new Intl.DateTimeFormat("es-CL", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric"
    }).format(new Date(`${value}T12:00:00`));
}

function resetSelection() {
    document.querySelectorAll(".time-slot").forEach((button) => {
        button.classList.remove("selected");
        button.setAttribute("aria-pressed", "false");
    });

    document.getElementById("summary-time").textContent = "Sin seleccionar";
    document.getElementById("selection-message").textContent =
        "Selecciona uno de los horarios disponibles.";
    clearButton.disabled = true;
}

function selectTime(button, time) {
    resetSelection();
    button.classList.add("selected");
    button.setAttribute("aria-pressed", "true");
    document.getElementById("summary-time").textContent = time;
    document.getElementById("selection-message").textContent =
        `Has seleccionado las ${time}. Es una preferencia de demostración, no una reserva.`;
    clearButton.disabled = false;
}

function renderSchedule() {
    slotsContainer.replaceChildren();
    resetSelection();

    document.getElementById("summary-artist").textContent =
        artist.options[artist.selectedIndex].textContent;

    if (!date.value || !date.validity.valid) {
        document.getElementById("summary-date").textContent = "Fecha no válida";
        document.getElementById("day-title").textContent = "Selecciona una fecha";
        document.getElementById("available-count").textContent = "";
        document.getElementById("selection-message").textContent =
            "Elige hoy o una fecha posterior.";
        return;
    }

    const formattedDate = formatDate(date.value);
    document.getElementById("summary-date").textContent = formattedDate;
    document.getElementById("day-title").textContent = formattedDate;

    const schedule = demoSchedules[artist.value];
    const total = schedule.morning.length + schedule.afternoon.length;
    document.getElementById("available-count").textContent =
        `${total - schedule.busy.length} disponibles`;

    // En esta maqueta se repite el horario de ejemplo para cada fecha.
    [["Mañana", schedule.morning], ["Tarde", schedule.afternoon]]
        .forEach(([label, times]) => {
            const heading = document.createElement("h3");
            heading.className = "period-title";
            heading.textContent = label;

            const grid = document.createElement("div");
            grid.className = "time-grid";

            times.forEach((time) => {
                const button = document.createElement("button");
                const busy = schedule.busy.includes(time);

                button.type = "button";
                button.className = "time-slot";
                button.textContent = time;
                button.disabled = busy;
                button.setAttribute("aria-pressed", "false");
                button.setAttribute(
                    "aria-label",
                    `${time}, ${busy ? "no disponible" : "disponible"}`
                );
                button.addEventListener("click", () => selectTime(button, time));
                grid.appendChild(button);
            });

            slotsContainer.append(heading, grid);
        });
}

artist.addEventListener("change", renderSchedule);
date.addEventListener("change", renderSchedule);
clearButton.addEventListener("click", resetSelection);
renderSchedule();

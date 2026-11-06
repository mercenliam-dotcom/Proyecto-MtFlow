"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const element = document.getElementById("agenda-calendar");
    if (!element || !window.FullCalendar) return;
    const calendar = new FullCalendar.Calendar(element, {
        initialView: window.innerWidth < 700 ? "listWeek" : "timeGridWeek",
        // Fechas civiles de Santiago: el servidor valida cambios de hora.
        // UTC evita que el navegador del visitante las convierta a otra zona.
        timeZone: "UTC", locale: "es", firstDay: 1, allDaySlot: false,
        height: 650, scrollTime: "08:00:00", editable: false, nowIndicator: false,
        now: element.dataset.today + "T12:00:00", buttonIcons: false,
        validRange: () => ({start: new Intl.DateTimeFormat("sv-SE", {timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date())}),
        headerToolbar: { left: "prev,next today", center: "title", right: "dayGridMonth,timeGridWeek,listWeek" },
        buttonText: { prev: "‹", next: "›", today: "Hoy", month: "Mes", week: "Semana", list: "Lista" },
        buttonHints: { prev: "Período anterior", next: "Período siguiente", today: "Ir a hoy" },
        noEventsText: "Sin horarios esta semana", events: element.dataset.events,
        eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
        slotLabelFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
        eventSourceFailure: () => { document.getElementById("agenda-error").textContent = "No se pudo cargar el calendario. Revisa la lista de horarios o vuelve a iniciar sesión."; },
        dateClick: info => {
            const ahora = new Intl.DateTimeFormat("sv-SE", {timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).format(new Date()).replace(" ","T");
            if (info.dateStr.slice(0,10) < ahora.slice(0,10) || (!info.allDay && info.dateStr.slice(0,16) <= ahora)) return;
            window.location.href = element.dataset.create + "?fecha=" + encodeURIComponent(info.dateStr.slice(0, 10));
        },
    });
    calendar.render();
});

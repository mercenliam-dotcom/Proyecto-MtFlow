"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const element = document.getElementById("agenda-calendar");
    if (!element || !window.FullCalendar) return;
    const reserva=element.dataset.mode === "reserva", fecha=document.getElementById("id_fecha");
    function fechaISO(){const m=fecha?.value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);return m?`${m[3]}-${m[2]}-${m[1]}`:element.dataset.today;}
    const calendar = new FullCalendar.Calendar(element, {
        initialView: reserva ? "timeGridDay" : window.innerWidth < 700 ? "listWeek" : "timeGridWeek",
        initialDate: reserva ? fechaISO() : element.dataset.today,
        // Fechas civiles de Santiago: el servidor valida cambios de hora.
        // UTC evita que el navegador del visitante las convierta a otra zona.
        timeZone: "UTC", locale: "es-CL", firstDay: 1, allDaySlot: false,
        titleFormat:{day:"2-digit",month:"long",year:"numeric"},
        // En «Mes» el encabezado es solo el día de la semana (la fecha va en cada casilla).
        dayHeaderContent:arg=>new Intl.DateTimeFormat("es-CL",arg.view.type==="dayGridMonth"?{weekday:"short",timeZone:"UTC"}:{weekday:"short",day:"2-digit",month:"2-digit",timeZone:"UTC"}).format(arg.date),
        height: 650, scrollTime: "08:00:00", editable: false, nowIndicator: false,
        now: element.dataset.today + "T12:00:00", buttonIcons: false,
        // Sin validRange: se puede revisar lo pasado; dateClick sigue sin crear horarios en el pasado.
        headerToolbar: { left: "prev,next today", center: "title", right: reserva ? "dayGridMonth,timeGridDay,listWeek" : "dayGridMonth,timeGridWeek,listWeek" },
        buttonText: { prev: "‹", next: "›", today: "Hoy", month: "Mes", week: "Semana", day:"Día", list: "Lista" },
        buttonHints: { prev: "Período anterior", next: "Período siguiente", today: "Ir a hoy" },
        noEventsText: "Sin horarios esta semana", events: element.dataset.events,
        eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
        slotLabelFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
        eventSourceFailure: () => { document.getElementById("agenda-error").textContent = "No se pudo cargar el calendario. Revisa la lista de horarios o vuelve a iniciar sesión."; },
        eventClick: info=>{if(reserva){info.jsEvent.preventDefault();document.getElementById("agenda-error").textContent=info.event.title;}},
        dateClick: info => {
            const ahora = new Intl.DateTimeFormat("sv-SE", {timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).format(new Date()).replace(" ","T");
            if (info.dateStr.slice(0,10) < ahora.slice(0,10) || (!info.allDay && info.dateStr.slice(0,16) <= ahora)) return;
            if(reserva){
                const [y,m,d]=info.dateStr.slice(0,10).split("-");fecha.value=`${d}/${m}/${y}`;
                if(!info.allDay) document.getElementById("id_hora_inicio").value=info.dateStr.slice(11,16);
                fecha.dispatchEvent(new Event("change"));
            }else window.location.href = element.dataset.create + "?fecha=" + encodeURIComponent(info.dateStr.slice(0, 10));
        },
    });
    calendar.render();
    if(reserva)fecha.addEventListener("change",()=>{if(fecha.checkValidity())calendar.gotoDate(fechaISO());});
});

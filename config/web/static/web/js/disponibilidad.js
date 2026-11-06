"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const root=document.getElementById("disponibilidad-calendario"), artista=document.getElementById("quote-artist"), fecha=document.getElementById("id_fecha_propuesta"), original=document.getElementById("id_hora_propuesta"), estado=document.getElementById("disponibilidad-estado");
    if (!root || !window.FullCalendar || !artista || !original) return;
    const hora=document.createElement("select");
    hora.name=original.name; hora.id=original.id; hora.className=original.className;
    let inicial=original.value.slice(0,5); original.replaceWith(hora);
    let peticionDia=0, peticionCalendario=0;
    function hoy() { return new Intl.DateTimeFormat("sv-SE",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date()); }
    function vaciar(mensaje) { hora.replaceChildren(new Option(mensaje,"")); }
    vaciar("Selecciona una fecha"); fecha.min=hoy();
    async function consultar(desde,hasta) {
        const url=new URL(root.dataset.url,window.location.origin);
        url.search=new URLSearchParams({tatuadora:artista.value,start:desde,end:hasta});
        const r=await fetch(url,{cache:"no-store",headers:{"Accept":"application/json"}});
        if (!r.ok) throw new Error("No se pudo consultar la disponibilidad. Reintenta o envía sin proponer horario.");
        return r.json();
    }
    async function cargarDia(preferida) {
        const turno=++peticionDia;
        if (!artista.value || !fecha.value) { vaciar("Selecciona tatuadora y fecha"); return; }
        const elegida=fecha.value;
        const siguiente=new Date(elegida+"T12:00:00Z"); siguiente.setUTCDate(siguiente.getUTCDate()+1);
        vaciar("Consultando horarios…"); hora.disabled=true;
        try {
            const datos=await consultar(elegida,siguiente.toISOString().slice(0,10));
            if(turno!==peticionDia) return;
            vaciar("Selecciona una hora disponible");
            const horas=new Set();
            for(const e of datos.eventos.filter(e=>e.extendedProps.disponible)) {
                const inicio=new Date(e.start+"Z").getTime(), fin=new Date(e.end+"Z").getTime();
                const ahora=new Date(datos.ahora+"Z").getTime();
                for(let t=Math.ceil(Math.max(inicio,ahora+1000)/1800000)*1800000;t<fin;t+=1800000) {
                    horas.add(new Date(t).toISOString().slice(11,16));
                }
            }
            for(const h of [...horas].sort()) hora.add(new Option(h,h));
            if(preferida && horas.has(preferida)) hora.value=preferida;
            estado.textContent=horas.size ? "Selecciona una hora como preferencia. No reserva ni bloquea la agenda." : "No hay horas disponibles ese día. Elige otra fecha o envía sin proponer horario.";
        } catch(e) { if(turno===peticionDia) { vaciar("No disponible"); estado.textContent=e.message; } }
        finally { if(turno===peticionDia) hora.disabled=false; }
    }
    const calendario=new FullCalendar.Calendar(root,{
        initialView:window.innerWidth<700 ? "timeGridDay" : "timeGridWeek", locale:"es",firstDay:1,timeZone:"UTC",allDaySlot:false,height:480,
        now:hoy()+"T12:00:00",validRange:()=>({start:hoy()}),slotMinTime:"10:00:00",slotMaxTime:"19:00:00",slotDuration:"00:30:00",editable:false,
        buttonIcons:false, headerToolbar:{left:"prev,next today",center:"title",right:"timeGridWeek,timeGridDay"},
        buttonText:{prev:"‹",next:"›",today:"Hoy",week:"Semana",day:"Día"},
        slotLabelFormat:{hour:"2-digit",minute:"2-digit",hour12:false},eventTimeFormat:{hour:"2-digit",minute:"2-digit",hour12:false},
        events:async(info,ok,fallo)=>{
            const turno=++peticionCalendario;
            if(!artista.value) { ok([]); return; }
            try {
                const datos=await consultar(info.startStr.slice(0,10),info.endStr.slice(0,10));
                if(turno!==peticionCalendario) { ok([]); return; }
                calendario.setOption("slotMinTime",datos.inicio); calendario.setOption("slotMaxTime",datos.fin);
                ok(datos.eventos);
            } catch(e) { estado.textContent=e.message; fallo(e); }
        },
        dateClick:info=>{ if(info.dateStr.slice(0,10)<hoy()) return; fecha.value=info.dateStr.slice(0,10); cargarDia(info.dateStr.slice(11,16)); },
        eventClick:info=>{
            if(!info.event.extendedProps.disponible) { estado.textContent="Ese intervalo está ocupado o bloqueado. Elige uno verde."; return; }
            fecha.value=info.event.startStr.slice(0,10); cargarDia();
        }
    });
    calendario.render();
    artista.addEventListener("change",()=>{ ++peticionDia; fecha.value=""; vaciar("Selecciona una fecha"); calendario.refetchEvents(); estado.textContent="Consulta el calendario de la tatuadora seleccionada."; });
    fecha.addEventListener("change",()=>{ if(fecha.value) calendario.gotoDate(fecha.value); cargarDia(); });
    document.getElementById("sin-horario").addEventListener("click",()=>{ ++peticionDia; fecha.value=""; vaciar("Sin preferencia de horario"); hora.disabled=false; });
    if(fecha.value) { calendario.gotoDate(fecha.value); cargarDia(inicial); }
    setInterval(()=>{fecha.min=hoy(); calendario.refetchEvents(); if(fecha.value) cargarDia(hora.value);},60000);
});

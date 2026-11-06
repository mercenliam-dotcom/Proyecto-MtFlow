"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const fecha = document.getElementById("id_fecha");
    const inicio = document.getElementById("id_hora_inicio");
    const fin = document.getElementById("id_hora_fin");
    if (!fecha || !inicio || !fin) return;
    function actualizar() {
        const partes = Object.fromEntries(new Intl.DateTimeFormat("sv-SE", {timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(new Date(Date.now()+60000)).map(p=>[p.type,p.value]));
        const hoy = `${partes.year}-${partes.month}-${partes.day}`;
        fecha.min = hoy;
        inicio.min = fecha.value === hoy ? `${partes.hour}:${partes.minute}` : "00:00";
        fin.min = inicio.value || inicio.min;
    }
    fecha.addEventListener("change",actualizar);
    inicio.addEventListener("change",actualizar);
    actualizar(); setInterval(actualizar,30000);
    const tipo=document.getElementById("id_tipo"), solicitud=document.getElementById("id_postulacion");
    function mostrar() {
        const cita=tipo.value==="CITA";
        solicitud.closest(".campo").hidden=!cita;
        solicitud.disabled=!cita;
        solicitud.required=cita;
    }
    tipo.addEventListener("change",mostrar); mostrar();
});

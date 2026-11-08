"use strict";
(() => {
    const recientes=new Map();
    function mostrar(texto,tipo="error") {
        const area=document.getElementById("avisos-temporales");
        texto=String(texto||"").replace(/\s+/g," ").trim().slice(0,280);
        if(!area || !texto || Date.now()-(recientes.get(texto)||0)<8000) return;
        recientes.set(texto,Date.now());
        if(recientes.size>100) recientes.delete(recientes.keys().next().value);
        while(area.children.length>=3) area.firstElementChild.remove();
        const aviso=document.createElement("div"), mensaje=document.createElement("p"), cerrar=document.createElement("button");
        aviso.className="aviso-temporal "+(tipo==="success" ? "aviso-temporal-ok" : "aviso-temporal-error");
        mensaje.textContent=texto; cerrar.type="button"; cerrar.textContent="×"; cerrar.setAttribute("aria-label","Cerrar aviso");
        aviso.append(mensaje,cerrar); area.append(aviso);
        let temporizador;
        const pausar=()=>clearTimeout(temporizador);
        const iniciar=()=>{pausar();temporizador=setTimeout(()=>aviso.remove(),7000);};
        cerrar.addEventListener("click",()=>{pausar();aviso.remove();});
        aviso.addEventListener("mouseenter",pausar);aviso.addEventListener("mouseleave",iniciar);
        aviso.addEventListener("focusin",pausar);aviso.addEventListener("focusout",iniciar);iniciar();
    }
    window.MTFlowAvisos={mostrar};
    document.addEventListener("DOMContentLoaded",()=>{
        const errores=".errorlist, .campo .error, .alerta-error, .error-message";
        if([...document.querySelectorAll(errores)].some(e=>!e.hidden && e.textContent.trim() && e.id!=="estado-conexion"))
            mostrar("Revisa los datos indicados. Los detalles del error permanecen junto al formulario.");
        document.querySelectorAll(".avisos .aviso").forEach(e=>mostrar(e.textContent,e.classList.contains("aviso-success")?"success":"error"));
        let pendiente;
        document.addEventListener("invalid",()=>{clearTimeout(pendiente);pendiente=setTimeout(()=>mostrar("Faltan datos o hay un valor incorrecto. Revisa los campos señalados antes de continuar."),50);},true);
        const conexion=document.getElementById("estado-conexion");
        function estado() {
            if(conexion) conexion.hidden=navigator.onLine;
            if(!navigator.onLine) mostrar("Sin conexión. Tus cambios no se enviarán automáticamente; conserva esta página abierta.");
        }
        window.addEventListener("offline",estado);
        window.addEventListener("online",()=>{estado();mostrar("La conexión volvió. Puedes reintentar la operación.","success");});
        estado();
        // Complementa los errores que ya presentan los componentes, sin retirarlos.
        for(const id of ["file-error","agenda-error","disponibilidad-estado","analysis-status"]) {
            const e=document.getElementById(id); if(!e) continue;
            new MutationObserver(()=>{const t=e.textContent.trim();if(/error|no pud|no se pudo|no disponible|sin conexión|no responde|falló|demoró|tardando|solo (jpg|png)|supera|excede/i.test(t)) mostrar(t);}).observe(e,{childList:true,subtree:true,characterData:true});
        }
    });
})();

"use strict";
document.addEventListener("DOMContentLoaded",()=>{
    const panel=document.getElementById("buzon-lectura"), contenido=document.getElementById("buzon-contenido"), error=document.getElementById("buzon-error");
    if(!panel) return;
    let controlador,ultima,version=0;
    async function abrir(enlace) {
        ultima=enlace; const actual=++version;
        if(controlador) controlador.abort(); controlador=new AbortController();
        const controladorActual=controlador;
        const limite=setTimeout(()=>controladorActual.abort(),15000);
        panel.setAttribute("aria-busy","true"); error.hidden=true;
        contenido.replaceChildren();const cargando=document.createElement("p");cargando.textContent="Cargando solicitud…";contenido.append(cargando);
        document.querySelectorAll(".buzon-fila.is-selected").forEach(e=>e.classList.remove("is-selected"));
        enlace.closest(".buzon-fila").classList.add("is-selected");
        try {
            const r=await fetch(enlace.dataset.resumenUrl,{signal:controlador.signal,cache:"no-store",credentials:"same-origin"});
            if(r.redirected) throw Error("Tu sesión pudo haber vencido. Abre el detalle completo para volver a ingresar.");
            if(!r.ok || r.headers.get("X-MTFlow-Fragment")!=="resumen-solicitud") throw Error(r.status===404 ? "Esta solicitud no está disponible para tu cuenta." : "No se pudo cargar el detalle. Puedes reintentar o abrir la página completa.");
            const doc=new DOMParser().parseFromString(await r.text(),"text/html"),fragmento=doc.querySelector("[data-resumen-solicitud]");
            if(actual!==version) return;
            if(!fragmento) throw Error("No se pudo mostrar el detalle. Abre la página completa.");
            contenido.replaceChildren(fragmento);
            const titulo=fragmento.querySelector("h2");titulo.focus({preventScroll:true});
            if(window.innerWidth<1000) panel.scrollIntoView({behavior:"smooth",block:"start"});
        } catch(e) {
            if(actual!==version) return;
            const mensaje=e.name==="AbortError" ? "La consulta tardó demasiado. Reintenta cuando el servidor responda." : e instanceof TypeError ? "No se pudo conectar con el servidor. Revisa la conexión y vuelve a intentar." : e.message;
            contenido.replaceChildren();error.querySelector("p").textContent=mensaje;error.hidden=false;
            error.querySelector("a").href=enlace.href;
            window.MTFlowAvisos?.mostrar(mensaje);
        } finally {clearTimeout(limite);if(actual===version)panel.removeAttribute("aria-busy");}
    }
    document.querySelectorAll("a[data-resumen-url]").forEach(a=>a.addEventListener("click",e=>{
        if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||e.button!==0) return;
        e.preventDefault();abrir(a);
    }));
    document.getElementById("buzon-reintentar").addEventListener("click",()=>{if(ultima)abrir(ultima);});
});

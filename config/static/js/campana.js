"use strict";
/* Campana de avisos: consulta cada 45 s las solicitudes sin leer y actualiza el contador. */
document.addEventListener("DOMContentLoaded", () => {
  const campana = document.getElementById("campana");
  if (!campana) return;
  const cuenta = document.getElementById("campana-cuenta");
  const lista = document.getElementById("campana-lista");
  const resumen = document.getElementById("campana-resumen");
  const form = document.getElementById("campana-form");
  const resumenBoton = campana.querySelector("summary");
  const tituloBase = document.title.replace(/^\(\d+\+?\)\s*/, "");
  let anterior = Number(cuenta.textContent.replace("+", "")) || 0;

  function pintar(datos) {
    const total = Number(datos.total) || 0;
    cuenta.hidden = total === 0;
    cuenta.textContent = total > 9 ? "9+" : String(total);
    resumen.textContent = total ? total + " sin leer" : "Al día";
    resumenBoton.setAttribute("aria-label", "Avisos de solicitudes nuevas: " + total + " sin leer");
    if (form) form.hidden = total === 0;
    document.title = (total ? "(" + (total > 9 ? "9+" : total) + ") " : "") + tituloBase;
    lista.replaceChildren();
    const items = Array.isArray(datos.items) ? datos.items : [];
    if (!items.length) {
      const li = document.createElement("li"); li.className = "campana-vacia";
      li.textContent = "No tienes solicitudes sin leer."; lista.append(li);
    }
    items.forEach((item) => {
      if (typeof item.url !== "string" || !item.url.startsWith("/panel/")) return;
      const li = document.createElement("li"), a = document.createElement("a"), punto = document.createElement("span"),
        texto = document.createElement("span"), nombre = document.createElement("strong"), detalle = document.createElement("small");
      a.href = item.url; punto.className = "campana-punto"; punto.setAttribute("aria-hidden", "true");
      nombre.textContent = item.nombre; detalle.textContent = item.detalle + " · " + item.hace;
      texto.append(nombre, detalle); a.append(punto, texto); li.append(a); lista.append(li);
    });
    if (total > anterior && items[0] && window.MTFlowAvisos) {
      window.MTFlowAvisos.mostrar("Nueva solicitud de " + items[0].nombre + ".", "success");
      campana.classList.remove("campana-sonando"); void campana.offsetWidth; campana.classList.add("campana-sonando");
    }
    anterior = total;
  }

  async function consultar() {
    if (document.hidden) return;
    try {
      const r = await fetch(campana.dataset.url, { headers: { Accept: "application/json" }, credentials: "same-origin", cache: "no-store" });
      if (r.ok) pintar(await r.json());
    } catch (e) { /* sin conexión: se reintenta en la próxima vuelta */ }
  }

  if (anterior) document.title = "(" + (anterior > 9 ? "9+" : anterior) + ") " + tituloBase;
  campana.addEventListener("toggle", () => { if (campana.open) consultar(); });
  setInterval(consultar, 45000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) consultar(); });
  document.addEventListener("click", (e) => { if (campana.open && !campana.contains(e.target)) campana.open = false; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && campana.open) { campana.open = false; resumenBoton.focus(); } });
});

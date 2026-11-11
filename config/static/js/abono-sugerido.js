"use strict";
/* Sugiere el abono (30 %, 35 % o 40 % del precio) con botones que rellenan el campo,
   y avisa en vivo si un monto escrito a mano queda fuera del rango. El servidor
   vuelve a validar el rango, así que esto solo ayuda a escribir. */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("form[data-abono-precio]");
  if (!form) return;
  const precioInput = form.querySelector("#id_precio_final");
  const abonoInput = form.querySelector("#id_abono_solicitado, #id_monto_abono");
  if (!abonoInput) return;
  const clp = (n) => "$" + Math.round(n).toLocaleString("es-CL");
  const caja = document.createElement("div");
  caja.className = "abono-sugerencias";
  const fila = document.createElement("div");
  fila.className = "abono-opciones";
  fila.setAttribute("role", "group");
  fila.setAttribute("aria-label", "Montos de abono sugeridos");
  const aviso = document.createElement("p");
  aviso.className = "abono-aviso";
  aviso.setAttribute("aria-live", "polite");
  caja.append(fila, aviso);
  (abonoInput.closest(".campo") || abonoInput).after(caja);

  function precio() {
    const valor = precioInput ? Number(precioInput.value) : Number(form.dataset.abonoPrecio);
    return Number.isFinite(valor) && valor > 0 ? Math.floor(valor) : 0;
  }
  function rango(p) { return [Math.ceil(p * 0.30), Math.floor(p * 0.40)]; }
  function redondear(monto, min, max) {
    const mil = Math.round(monto / 1000) * 1000;   // montos redondos cuando caben en el rango
    return mil >= min && mil <= max ? mil : Math.min(max, Math.max(min, Math.round(monto)));
  }

  function pintar() {
    const p = precio();
    fila.replaceChildren();
    if (!p) { aviso.textContent = precioInput ? "Escribe el precio total para ver los abonos sugeridos." : ""; aviso.className = "abono-aviso"; return; }
    const [min, max] = rango(p);
    [30, 35, 40].forEach((pct) => {
      const monto = pct === 30 ? redondear(Math.ceil(p * 0.30 / 1000) * 1000, min, max)
                  : pct === 40 ? redondear(Math.floor(p * 0.40 / 1000) * 1000, min, max)
                  : redondear(p * 0.35, min, max);
      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = "abono-opcion";
      boton.textContent = pct + " % · " + clp(monto);
      boton.setAttribute("aria-pressed", String(Number(abonoInput.value) === monto));
      boton.addEventListener("click", () => { abonoInput.value = String(monto); abonoInput.dispatchEvent(new Event("input", { bubbles: true })); abonoInput.focus(); });
      fila.append(boton);
    });
    const valor = Number(abonoInput.value);
    if (abonoInput.value === "") {
      aviso.textContent = "Elige una opción o escribe otro monto entre " + clp(min) + " y " + clp(max) + ".";
      aviso.className = "abono-aviso";
    } else if (valor < min || valor > max) {
      aviso.textContent = "Fuera del rango: el abono debe estar entre " + clp(min) + " y " + clp(max) + " (30 %–40 %).";
      aviso.className = "abono-aviso abono-fuera";
    } else {
      aviso.textContent = "Abono de " + clp(valor) + " (" + (valor * 100 / p).toFixed(1).replace(".", ",") + " % del precio). Resta " + clp(p - valor) + ".";
      aviso.className = "abono-aviso abono-ok";
    }
  }
  if (precioInput) precioInput.addEventListener("input", pintar);
  abonoInput.addEventListener("input", pintar);
  pintar();
});

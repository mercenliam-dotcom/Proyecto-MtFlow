"use strict";
const carrusel = document.getElementById("carrusel");
if (carrusel) {
  const reducir = matchMedia("(prefers-reduced-motion: reduce)");
  const mover = (sentido) => {
    const final = carrusel.scrollWidth - carrusel.clientWidth;
    const siguiente = carrusel.scrollLeft + sentido * carrusel.clientWidth;
    carrusel.scrollTo({left: siguiente > final + 20 ? 0 : siguiente < -20 ? final : siguiente,
      behavior: reducir.matches ? "instant" : "smooth"});
  };

  // Avance automático cada 5 s. Se pausa con el mouse encima, al enfocar o tocar
  // el carrusel, con la pestaña oculta y si la persona pidió reducir el movimiento.
  const INTERVALO = 5000;
  const diapositivas = carrusel.querySelectorAll(".mt-diapositiva").length;
  let temporizador = null, pausado = false;
  const detener = () => { clearInterval(temporizador); temporizador = null; };
  const iniciar = () => {
    detener();
    if (diapositivas < 2 || pausado || reducir.matches || document.hidden) return;
    temporizador = setInterval(() => mover(1), INTERVALO);
  };
  const pausar = () => { pausado = true; detener(); };
  const reanudar = () => { pausado = false; iniciar(); };

  document.getElementById("carrusel-anterior").addEventListener("click", () => { mover(-1); iniciar(); });
  document.getElementById("carrusel-siguiente").addEventListener("click", () => { mover(1); iniciar(); });
  const zona = carrusel.closest("section") || carrusel;
  zona.addEventListener("mouseenter", pausar);
  zona.addEventListener("mouseleave", reanudar);
  zona.addEventListener("focusin", pausar);
  zona.addEventListener("focusout", (e) => { if (!zona.contains(e.relatedTarget)) reanudar(); });
  carrusel.addEventListener("touchstart", pausar, {passive: true});
  carrusel.addEventListener("touchend", () => setTimeout(reanudar, INTERVALO), {passive: true});
  document.addEventListener("visibilitychange", iniciar);
  reducir.addEventListener?.("change", iniciar);
  iniciar();
}

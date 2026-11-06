"use strict";
const carrusel = document.getElementById("carrusel");
if (carrusel) {
  const mover = (sentido) => {
    const final = carrusel.scrollWidth - carrusel.clientWidth;
    const siguiente = carrusel.scrollLeft + sentido * carrusel.clientWidth;
    carrusel.scrollTo({left: siguiente > final + 20 ? 0 : siguiente < -20 ? final : siguiente,
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
  };
  document.getElementById("carrusel-anterior").addEventListener("click", () => mover(-1));
  document.getElementById("carrusel-siguiente").addEventListener("click", () => mover(1));
}

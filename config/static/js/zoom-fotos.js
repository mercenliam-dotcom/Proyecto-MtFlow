"use strict";
// Zoom a pantalla completa (PhotoSwipe, copiado en static/vendor/photoswipe).
// Las rutas llegan desde la plantilla con {% static %} para que funcionen
// también con los nombres versionados de producción.
(function () {
    const script = document.currentScript;
    if (!script) return;
    const lightboxUrl = script.dataset.lightbox, coreUrl = script.dataset.core;
    const iniciar = () => {
        const galerias = document.querySelectorAll("[data-galeria-zoom]");
        if (!galerias.length) return;
        import(lightboxUrl).then(({ default: PhotoSwipeLightbox }) => {
            galerias.forEach(galeria => {
                const lightbox = new PhotoSwipeLightbox({
                    gallery: galeria,
                    // Cada galería puede indicar qué enlaces incluir (p. ej. solo tarjetas visibles).
                    children: galeria.dataset.galeriaZoom || "a[data-zoom]",
                    pswpModule: () => import(coreUrl),
                    bgOpacity: 0.94,
                    showHideAnimationType: "zoom",
                    closeTitle: "Cerrar", zoomTitle: "Acercar", arrowPrevTitle: "Anterior", arrowNextTitle: "Siguiente",
                    errorMsg: "No se pudo cargar la imagen.",
                });
                // Si la plantilla no conoce el tamaño, se toma de la imagen ya cargada.
                lightbox.addFilter("domItemData", (item, elemento, enlace) => {
                    if (!item.width || !item.height) {
                        const img = enlace.querySelector("img");
                        item.width = img?.naturalWidth || 1200;
                        item.height = img?.naturalHeight || 1200;
                    }
                    const pie = enlace.dataset.titulo;
                    if (pie) item.alt = pie;
                    return item;
                });
                lightbox.init();
            });
        }).catch(() => { /* Sin zoom: los enlaces abren la imagen normalmente. */ });
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
    else iniciar();
})();

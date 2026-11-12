"use strict";
// Gráfico de tendencia en Métricas (Chart.js, copiado en static/vendor/chartjs).
document.addEventListener("DOMContentLoaded", () => {
    const lienzo = document.getElementById("grafico-tendencia");
    const fuente = document.getElementById("datos-tendencia");
    if (!lienzo || !fuente || !window.Chart) return;
    const datos = JSON.parse(fuente.textContent);
    const quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const tinta = "#696472", rejilla = "rgba(41, 38, 49, .08)";
    // Paleta validada (daltonismo y contraste): morado de la marca + ámbar.
    const MORADO = "#62418b", AMBAR = "#b07a2e";
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.color = tinta;
    new Chart(lienzo, {
        data: {
            labels: datos.etiquetas,
            datasets: [
                { type: "bar", label: "Recibidas", data: datos.recibidas, backgroundColor: MORADO, hoverBackgroundColor: "#4d306f",
                  borderRadius: { topLeft: 4, topRight: 4 }, borderSkipped: "bottom", maxBarThickness: 26, order: 2 },
                { type: "line", label: "Terminados", data: datos.terminados, borderColor: AMBAR, backgroundColor: AMBAR,
                  borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, pointBackgroundColor: AMBAR,
                  pointBorderColor: "#fffefa", pointBorderWidth: 2, cubicInterpolationMode: "monotone", order: 1 },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: quieto ? false : { duration: 700, easing: "easeOutCubic" },
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { position: "top", align: "end", labels: { usePointStyle: true, boxWidth: 8, boxHeight: 8, padding: 16, sort: (a, b) => a.datasetIndex - b.datasetIndex } },
                tooltip: { backgroundColor: "#292631", padding: 10, cornerRadius: 8, boxPadding: 4, usePointStyle: true,
                           callbacks: { title: items => `Semana del ${items[0].label}` } },
            },
            scales: {
                x: { grid: { display: false }, border: { color: rejilla } },
                y: { beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: rejilla }, border: { display: false } },
            },
        },
    });
});

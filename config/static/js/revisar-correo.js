"use strict";
// Revisión automática del correo mientras se escribe: consulta si el dominio
// recibe correos (apps/cuentas/verificacion_correo.py) y sugiere correcciones
// como «gmial.com» → «gmail.com». El servidor lo vuelve a revisar al enviar.
(function () {
    const url = document.body.dataset.revisarCorreo;
    if (!url) return;
    const ESPERA = 700;

    function iniciar(campo) {
        let temporizador = null, revisado = "", pedido = 0;
        const estado = document.createElement("small");
        estado.className = "estado-correo";
        estado.setAttribute("role", "status");
        estado.setAttribute("aria-live", "polite");
        estado.hidden = true;
        campo.after(estado);

        function mostrar(tipo, texto, sugerencia) {
            campo.dataset.correoEstado = tipo;
            campo.dataset.correoMensaje = tipo === "error" ? texto : "";
            campo.setCustomValidity(tipo === "error" ? texto : "");
            estado.dataset.tipo = tipo;
            estado.textContent = texto;
            estado.hidden = !texto;
            if (sugerencia) {
                const boton = document.createElement("button");
                boton.type = "button";
                boton.className = "usar-sugerencia";
                boton.textContent = `Usar ${sugerencia}`;
                boton.addEventListener("click", () => {
                    campo.value = sugerencia;
                    campo.dispatchEvent(new Event("input", { bubbles: true }));
                    revisar();
                    campo.focus();
                });
                estado.append(" ", boton);
            }
        }
        function limpiar() {
            delete campo.dataset.correoEstado;
            campo.setCustomValidity("");
            estado.hidden = true;
        }
        function formatoValido(valor) {
            return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(valor);
        }
        async function revisar() {
            clearTimeout(temporizador);
            const valor = campo.value.trim().toLowerCase();
            if (!valor || !formatoValido(valor) || valor === revisado) return;
            revisado = valor;
            const numero = ++pedido;
            mostrar("revisando", "Revisando el correo…");
            try {
                const r = await fetch(`${url}?email=${encodeURIComponent(valor)}`, { credentials: "same-origin", headers: { Accept: "application/json" } });
                const datos = await r.json();
                if (numero !== pedido) return; // llegó una respuesta vieja
                if (datos.ok) mostrar("ok", "✓ El dominio del correo es válido.");
                else mostrar("error", datos.mensaje, datos.sugerencia);
            } catch (_) {
                if (numero === pedido) limpiar(); // sin conexión: no se bloquea
            }
        }
        campo.addEventListener("input", () => {
            if (campo.value.trim().toLowerCase() !== revisado) { revisado = ""; limpiar(); }
            clearTimeout(temporizador);
            temporizador = setTimeout(revisar, ESPERA);
        });
        campo.addEventListener("blur", revisar);
        if (campo.value && !campo.readOnly && !campo.disabled) revisar();
    }

    document.querySelectorAll("input[type=email]:not([readonly]):not([disabled]):not([data-sin-revision])").forEach(iniciar);
})();

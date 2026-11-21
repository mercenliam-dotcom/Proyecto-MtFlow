"use strict";
// Reglas de escritura y mensajes de validación en español para todo el sitio.
//
// 1. Bloquea al escribir (y al pegar) los caracteres que un campo no admite:
//      data-solo="letras"   nombres y apellidos: letras y un espacio entre palabras
//      data-solo="digitos"  teléfono y otros números
//      data-solo="usuario"  nombre de usuario: minúsculas sin tilde y números
//      data-solo="social"   usuario de Instagram o TikTok: letras, números, punto y guion bajo
//      data-mascara="fecha" DD/MM/AAAA (agrega las barras sola)
// 2. Reemplaza los avisos del navegador (que salen en su idioma: «Please fill out
//    this field») por mensajes propios en español bajo cada campo.
// 3. Fechas «espejo»: un campo DD/MM/AAAA visible que alimenta uno oculto AAAA-MM-DD
//    usado por los calendarios.
(function () {
    const LETRA = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ";
    const AVISOS = {
        letras: "Solo letras, con un espacio entre palabras.",
        digitos: "Solo números.",
        usuario: "Solo letras minúsculas sin tilde y números.",
        social: "Solo letras, números, punto y guion bajo.",
        fecha: "Solo números: el formato es DD/MM/AAAA.",
    };

    function limpiar(tipo, valor) {
        switch (tipo) {
            case "letras":
                return valor.replace(new RegExp(`[^${LETRA} ]`, "g"), "").replace(/^ +/, "").replace(/ {2,}/g, " ");
            case "digitos":
                return valor.replace(/\D/g, "");
            case "usuario":
                return valor.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");
            case "social":
                return valor.replace(/[^A-Za-z0-9._@]/g, "").replace(/(?!^)@/g, "");
            case "fecha": {
                const d = valor.replace(/\D/g, "").slice(0, 8);
                return d.length > 4 ? `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}` : d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
            }
        }
        return valor;
    }

    // Aviso breve junto al campo cuando se bloquea un carácter.
    const temporizadores = new WeakMap();
    function avisoBreve(control, texto) {
        const contenedor = control.closest(".campo, .form-group, .telefono-cl") || control.parentElement;
        let aviso = contenedor.querySelector(":scope > .aviso-tecleo");
        if (!aviso) {
            aviso = document.createElement("small");
            aviso.className = "aviso-tecleo";
            aviso.setAttribute("role", "status");
            (control.closest(".telefono-cl") || control).after(aviso);
        }
        aviso.textContent = texto;
        aviso.hidden = false;
        clearTimeout(temporizadores.get(control));
        temporizadores.set(control, setTimeout(() => { aviso.hidden = true; }, 2200));
    }

    function tipoDe(control) {
        return control.dataset.solo || (control.dataset.mascara === "fecha" ? "fecha" : null);
    }

    document.addEventListener("input", (e) => {
        const control = e.target;
        const tipo = control instanceof HTMLInputElement && tipoDe(control);
        if (!tipo) return;
        const antes = control.value;
        const despues = limpiar(tipo, antes);
        if (despues === antes) return;
        // Mantiene el cursor donde estaba, descontando lo que se quitó antes de él.
        const cursor = control.selectionStart ?? antes.length;
        const previo = antes.slice(0, cursor);
        const posicion = Math.max(0, Math.min(despues.length, cursor - (previo.length - limpiar(tipo, previo).length)));
        control.value = despues;
        if (tipo === "fecha") return;
        try { control.setSelectionRange(posicion, posicion); } catch (_) { /* tipos sin selección */ }
        if (despues.length < antes.length) avisoBreve(control, AVISOS[tipo]);
    }, true);

    // Campos type="number": el navegador ya bloquea letras, pero deja pasar
    // «e», «+» y «-» (notación científica). Se bloquean, y el punto/coma en enteros.
    document.addEventListener("keydown", (e) => {
        const c = e.target;
        if (!(c instanceof HTMLInputElement) || c.type !== "number" || e.ctrlKey || e.metaKey || e.key.length !== 1) return;
        const entero = !c.step || c.step === "1";
        if (/[eE+\-]/.test(e.key) || (entero && /[.,]/.test(e.key))) {
            e.preventDefault();
            avisoBreve(c, entero ? "Solo números enteros." : "Solo números (usa punto para los decimales).");
        }
    }, true);

    // ---------------------------------------------------------------
    // Mensajes de validación en español
    // ---------------------------------------------------------------
    function mensaje(c) {
        const v = c.validity;
        if (v.valueMissing) {
            if (c.type === "checkbox") return "Marca esta casilla para continuar.";
            if (c.type === "radio") return "Elige una de las opciones.";
            if (c.type === "file") return "Selecciona un archivo.";
            if (c.tagName === "SELECT") return "Selecciona una opción de la lista.";
            return "Completa este campo.";
        }
        if (v.customError) return c.validationMessage;
        if (v.typeMismatch) return c.type === "email" ? "Escribe un correo válido, por ejemplo nombre@correo.cl." : "Revisa el formato de este campo.";
        if (v.patternMismatch) return c.dataset.mensajePatron || c.title || "El formato no es válido.";
        if (v.tooShort) return `Escribe al menos ${c.minLength} caracteres (ahora tiene ${c.value.length}).`;
        if (v.tooLong) return `Escribe como máximo ${c.maxLength} caracteres.`;
        if (v.rangeUnderflow) return `El valor mínimo es ${c.min}.`;
        if (v.rangeOverflow) return `El valor máximo es ${c.max}.`;
        if (v.stepMismatch) return "Usa un valor válido para este campo.";
        if (v.badInput) return c.type === "number" ? "Escribe solo números." : "Revisa el valor de este campo.";
        return "Revisa este campo.";
    }

    function contenedorDe(c) {
        return c.closest(".campo, .form-group, fieldset, p, label") || c.parentElement;
    }
    function quitarError(c) {
        const caja = document.getElementById(`${c.id || c.name}-error-es`);
        if (caja) caja.remove();
        c.removeAttribute("aria-invalid");
    }
    let enfocado = false;
    document.addEventListener("invalid", (e) => {
        const c = e.target;
        // El formulario de solicitud por pasos ya muestra sus propios mensajes.
        if (c.closest("#quote-form")) return;
        e.preventDefault(); // sin el globo del navegador (que sale en su idioma)
        quitarError(c);
        const caja = document.createElement("div");
        caja.className = "error error-es";
        caja.id = `${c.id || c.name}-error-es`;
        caja.textContent = mensaje(c);
        (c.closest(".telefono-cl") || c).after(caja);
        c.setAttribute("aria-invalid", "true");
        c.setAttribute("aria-describedby", [c.getAttribute("aria-describedby"), caja.id].filter(Boolean).join(" "));
        if (!enfocado) {
            enfocado = true;
            c.focus({ preventScroll: true });
            contenedorDe(c).scrollIntoView({ block: "center", behavior: "smooth" });
            setTimeout(() => { enfocado = false; }, 0);
        }
    }, true);
    ["input", "change"].forEach((evento) => document.addEventListener(evento, (e) => {
        if (e.target.matches && e.target.matches("input, select, textarea") && e.target.validity && e.target.validity.valid) quitarError(e.target);
    }));

    // ---------------------------------------------------------------
    // Fechas espejo: visible DD/MM/AAAA ↔ oculto AAAA-MM-DD
    // ---------------------------------------------------------------
    function aTexto(iso) {
        const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
        return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
    }
    function aIso(texto) {
        const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(texto || "");
        if (!m) return "";
        const f = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1]));
        return f.getUTCDate() === +m[1] && f.getUTCMonth() === +m[2] - 1 ? `${m[3]}-${m[2]}-${m[1]}` : "";
    }
    document.querySelectorAll("input[data-espejo-de]").forEach((visible) => {
        const oculto = document.getElementById(visible.dataset.espejoDe);
        if (!oculto) return;
        // Los calendarios cambian el valor oculto por código: se refleja siempre en el visible.
        const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
        Object.defineProperty(oculto, "value", {
            configurable: true,
            get() { return descriptor.get.call(this); },
            set(v) { descriptor.set.call(this, v); if (document.activeElement !== visible) visible.value = aTexto(v); },
        });
        visible.value = aTexto(oculto.value);
        visible.addEventListener("input", () => {
            visible.setCustomValidity("");
            const iso = aIso(visible.value);
            if (visible.value === "" || iso) {
                descriptor.set.call(oculto, iso);
                oculto.dispatchEvent(new Event("change", { bubbles: true }));
            }
        });
        visible.addEventListener("blur", () => {
            if (visible.value && !aIso(visible.value)) {
                visible.setCustomValidity("Escribe una fecha válida con el formato DD/MM/AAAA.");
                visible.reportValidity();
            } else visible.setCustomValidity("");
        });
    });
})();

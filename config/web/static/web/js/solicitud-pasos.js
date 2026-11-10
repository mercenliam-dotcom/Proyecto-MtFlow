"use strict";
/*
 * Solicitud por pasos (mejora progresiva).
 *
 * Sin JavaScript el formulario se ve completo y funciona igual. Con JavaScript:
 *  - se muestra un paso a la vez, con barra de progreso y botones Atrás/Siguiente;
 *  - cada paso se valida antes de avanzar (mensajes en español junto al campo);
 *  - las listas desplegables cortas se reemplazan por tarjetas táctiles;
 *  - el calendario se abre en una ventana emergente;
 *  - el último paso muestra un resumen editable antes de enviar;
 *  - el botón "atrás" del navegador o del celular retrocede un paso.
 * No cambia nombres ni valores de los campos: el servidor recibe lo mismo.
 */
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("quote-form");
    if (!form) return;
    const pasos = [...form.querySelectorAll(".paso")];
    const total = pasos.length;
    const nav = document.getElementById("pasos");
    const acciones = document.getElementById("pasos-acciones");
    const atras = document.getElementById("paso-atras");
    const siguiente = document.getElementById("paso-siguiente");
    const progreso = document.getElementById("pasos-progreso");
    const numero = document.getElementById("paso-numero");
    const nombrePaso = document.getElementById("paso-nombre");
    const resumenRevision = document.getElementById("resumen-revision");
    const resumenVivo = document.getElementById("resumen-vivo");
    const resumenVivoContenido = document.getElementById("resumen-vivo-contenido");
    const movimientoReducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const exito = document.getElementById("dialogo-exito");
    let actual = 1;
    let maximoVisitado = 1;

    // ------------------------------------------------------------------
    // Ventanas emergentes
    // ------------------------------------------------------------------
    function abrir(dialogo) {
        if (!dialogo || dialogo.open) return;
        if (typeof dialogo.showModal === "function") dialogo.showModal();
        else dialogo.setAttribute("open", "");
        document.body.classList.add("con-dialogo");
    }
    function cerrar(dialogo) {
        if (!dialogo) return;
        if (typeof dialogo.close === "function" && dialogo.open) dialogo.close();
        else dialogo.removeAttribute("open");
    }
    document.querySelectorAll("dialog.dialogo").forEach((dialogo) => {
        dialogo.addEventListener("close", () => document.body.classList.remove("con-dialogo"));
        dialogo.addEventListener("click", (e) => {
            if (e.target.closest("[data-cerrar]")) cerrar(dialogo);
            // Tocar fuera del contenido cierra (excepto el de "enviando")
            else if (e.target === dialogo && dialogo.id !== "dialogo-enviando") cerrar(dialogo);
        });
    });
    const enviando = document.getElementById("dialogo-enviando");
    if (enviando) enviando.addEventListener("cancel", (e) => e.preventDefault());

    // Tras enviar con éxito: aviso emergente y acceso directo a la estimación
    if (exito) {
        abrir(exito);
        const ver = exito.querySelector("[data-ver-estimacion]");
        if (ver) ver.addEventListener("click", () => {
            const tarjeta = document.getElementById("quote-summary");
            tarjeta.scrollIntoView({ behavior: movimientoReducido ? "auto" : "smooth", block: "start" });
            document.getElementById("summary-heading").focus({ preventScroll: true });
        });
    }

    // ------------------------------------------------------------------
    // Tarjetas táctiles en lugar de listas desplegables
    // ------------------------------------------------------------------
    function campoDe(control) { return control.closest(".campo") || control.closest(".check-field") || control.parentElement; }

    function tarjetas(select, opciones = {}) {
        if (!select || select.dataset.tarjetas) return;
        select.dataset.tarjetas = "1";
        const etiqueta = form.querySelector(`label[for="${select.id}"]`);
        const grupo = document.createElement("div");
        grupo.className = "opciones" + (opciones.compactas ? " opciones-compactas" : "");
        grupo.setAttribute("role", "radiogroup");
        if (etiqueta) {
            etiqueta.id = etiqueta.id || `${select.id}-etiqueta`;
            grupo.setAttribute("aria-labelledby", etiqueta.id);
        }
        const botones = [];
        for (const opcion of select.options) {
            if (!opcion.value) continue;
            const b = document.createElement("button");
            b.type = "button";
            b.className = "opcion";
            b.setAttribute("role", "radio");
            b.dataset.valor = opcion.value;
            b.textContent = opcion.textContent;
            botones.push(b);
            grupo.append(b);
        }
        function sincronizar() {
            botones.forEach((b) => {
                const activo = b.dataset.valor === select.value;
                b.setAttribute("aria-checked", String(activo));
                b.tabIndex = activo || (!select.value && b === botones[0]) ? 0 : -1;
            });
        }
        function elegir(b) {
            select.value = b.dataset.valor;
            select.dispatchEvent(new Event("change", { bubbles: true }));
            sincronizar();
            limpiarError(select);
        }
        grupo.addEventListener("click", (e) => { const b = e.target.closest(".opcion"); if (b) elegir(b); });
        grupo.addEventListener("keydown", (e) => {
            const i = botones.indexOf(document.activeElement);
            if (i < 0) return;
            const salto = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
            if (!salto) return;
            e.preventDefault();
            const b = botones[(i + salto + botones.length) % botones.length];
            b.focus(); elegir(b);
        });
        select.addEventListener("change", sincronizar);
        select.classList.add("select-reemplazado");
        select.tabIndex = -1;
        select.setAttribute("aria-hidden", "true");
        select.after(grupo);
        select.tarjetas = grupo;
        sincronizar();
    }

    tarjetas(document.getElementById("quote-artist"));
    tarjetas(document.getElementById("body-zone"), { compactas: true });
    tarjetas(form.elements.namedItem("color"));
    tarjetas(form.elements.namedItem("detalle"));
    tarjetas(form.elements.namedItem("canal_preferido"), { compactas: true });

    // Teclados adecuados en el celular
    for (const nombre of ["alto_cm", "ancho_cm"]) {
        const c = form.elements.namedItem(nombre);
        if (c) c.setAttribute("inputmode", "decimal");
    }
    const presupuesto = form.elements.namedItem("presupuesto");
    if (presupuesto) { presupuesto.setAttribute("inputmode", "numeric"); presupuesto.placeholder = presupuesto.placeholder || "Ej: 120000"; }

    // Usuario de redes solo cuando el canal es Instagram o TikTok
    const canal = form.elements.namedItem("canal_preferido");
    const usuarioSocial = form.elements.namedItem("usuario_social");
    function alternarUsuarioSocial() {
        if (!canal || !usuarioSocial) return;
        const red = canal.value === "instagram" || canal.value === "tiktok";
        const conError = campoDe(usuarioSocial).classList.contains("con-error");
        campoDe(usuarioSocial).hidden = !red && !conError && !usuarioSocial.value;
    }
    if (canal) canal.addEventListener("change", alternarUsuarioSocial);
    alternarUsuarioSocial();

    // ------------------------------------------------------------------
    // Validación por paso, con mensajes claros
    // ------------------------------------------------------------------
    function mensaje(control) {
        const v = control.validity;
        if (v.valueMissing) return control.tagName === "SELECT" ? "Elige una opción." : control.type === "file" ? "Selecciona una imagen." : "Completa este campo.";
        if (v.typeMismatch) return control.type === "email" ? "Escribe un correo válido, por ejemplo nombre@correo.cl." : "Revisa el formato.";
        if (v.rangeUnderflow) return `Debe ser al menos ${control.min}.`;
        if (v.rangeOverflow) return `Debe ser como máximo ${control.max}.`;
        if (v.stepMismatch || v.badInput) return "Escribe solo números (usa punto para decimales).";
        if (v.patternMismatch) return "Revisa el formato.";
        if (v.tooLong) return `Máximo ${control.maxLength} caracteres.`;
        return control.validationMessage || "Revisa este campo.";
    }
    function marcarError(control, texto) {
        const campo = campoDe(control);
        campo.classList.add("con-error");
        let caja = campo.querySelector(".error-js");
        if (!caja) { caja = document.createElement("div"); caja.className = "error error-js"; caja.id = `${control.id}-error-js`; campo.append(caja); }
        caja.textContent = texto;
        control.setAttribute("aria-invalid", "true");
        control.setAttribute("aria-describedby", [control.getAttribute("aria-describedby"), caja.id].filter(Boolean).join(" "));
    }
    function limpiarError(control) {
        const campo = campoDe(control);
        const caja = campo && campo.querySelector(".error-js");
        if (caja) caja.remove();
        if (campo && !campo.querySelector(".error:not(.error-js)")) campo.classList.remove("con-error");
        control.removeAttribute("aria-invalid");
    }
    form.addEventListener("input", (e) => { if (e.target.matches("input, textarea, select")) limpiarError(e.target); actualizarResumenes(); });
    form.addEventListener("change", (e) => { if (e.target.matches("input, textarea, select")) limpiarError(e.target); actualizarResumenes(); });

    function validarPaso(n, enfocar = true) {
        const paso = pasos[n - 1];
        let primero = null;
        for (const control of paso.querySelectorAll("input, select, textarea")) {
            if (control.type === "hidden" || control.disabled || campoDe(control).hidden) continue;
            if (control.type === "file") continue; // la imagen se valida aparte
            // validity.valid no dispara el evento "invalid" (evita el aviso flotante duplicado)
            if (!control.validity.valid) {
                marcarError(control, mensaje(control));
                primero = primero || control;
            }
        }
        if (n === 2) {
            const archivo = document.getElementById("reference");
            const preview = document.getElementById("reference-preview");
            const lista = archivo.files.length && !preview.hidden && preview.getAttribute("src");
            if (!lista) {
                document.getElementById("file-error").textContent = "Selecciona una imagen JPG o PNG para continuar.";
                primero = primero || archivo;
            }
        }
        if (primero && enfocar) {
            const destino = primero.classList.contains("select-reemplazado") ? primero.tarjetas.querySelector(".opcion") : primero;
            destino.focus({ preventScroll: true });
            campoDe(primero).scrollIntoView({ behavior: movimientoReducido ? "auto" : "smooth", block: "center" });
        }
        return !primero;
    }

    // ------------------------------------------------------------------
    // Navegación entre pasos
    // ------------------------------------------------------------------
    function ir(n, { historial = true, enfocar = true } = {}) {
        n = Math.min(Math.max(n, 1), total);
        actual = n;
        maximoVisitado = Math.max(maximoVisitado, n);
        pasos.forEach((p, i) => {
            const activo = i + 1 === n;
            p.classList.toggle("activo", activo);
            p.hidden = !activo;
        });
        nav.querySelectorAll("[data-ir]").forEach((b) => {
            const destino = Number(b.dataset.ir);
            b.classList.toggle("hecho", destino < n);
            b.disabled = destino > maximoVisitado;
            if (destino === n) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
        });
        progreso.style.width = `${(n / total) * 100}%`;
        numero.textContent = n;
        nombrePaso.textContent = pasos[n - 1].dataset.titulo;
        atras.hidden = n === 1;
        siguiente.hidden = n === total;
        acciones.classList.toggle("ultimo", n === total);
        if (n === total) construirRevision();
        actualizarResumenes();
        if (historial) history.pushState({ paso: n, prof: ((history.state && history.state.prof) || 0) + 1 }, "", `#paso-${n}`);
        if (enfocar) {
            nav.scrollIntoView({ behavior: movimientoReducido ? "auto" : "smooth", block: "start" });
            pasos[n - 1].querySelector("legend").focus({ preventScroll: true });
        }
    }

    function avanzar() {
        if (!validarPaso(actual)) return;
        ir(actual + 1);
    }
    siguiente.addEventListener("click", avanzar);
    // "Atrás" usa el historial solo si el paso anterior se abrió desde esta página;
    // nunca saca a la persona del formulario.
    atras.addEventListener("click", () => {
        if (history.state && history.state.prof > 0) history.back();
        else { ir(actual - 1, { historial: false }); history.replaceState({ paso: actual, prof: 0 }, "", `#paso-${actual}`); }
    });
    nav.addEventListener("click", (e) => {
        const b = e.target.closest("[data-ir]");
        if (!b || b.disabled) return;
        const destino = Number(b.dataset.ir);
        if (destino > actual) {
            for (let n = actual; n < destino; n++) if (!validarPaso(n)) { if (n !== actual) ir(n); return; }
        }
        ir(destino);
    });
    window.addEventListener("popstate", (e) => {
        if (e.state && e.state.paso) ir(e.state.paso, { historial: false });
    });

    // Enter en un campo avanza en vez de enviar a medias
    form.addEventListener("keydown", (e) => {
        if (e.key !== "Enter" || e.target.tagName === "TEXTAREA" || e.target.tagName === "BUTTON") return;
        if (actual < total) { e.preventDefault(); avanzar(); }
    });

    // Antes que cualquier otro manejador: solo se envía desde el último paso
    // y con todos los pasos válidos.
    document.addEventListener("submit", (e) => {
        if (e.target !== form) return;
        if (actual < total) { e.preventDefault(); e.stopPropagation(); avanzar(); return; }
        for (let n = 1; n < total; n++) {
            if (!validarPaso(n, false)) { e.preventDefault(); e.stopPropagation(); ir(n); validarPaso(n); return; }
        }
    }, true);
    // Después de las comprobaciones de cotizacion.js: ventana de "enviando"
    form.addEventListener("submit", (e) => {
        if (e.defaultPrevented) { if (!document.getElementById("reference").files.length) ir(2); return; }
        abrir(enviando);
    });
    window.addEventListener("pageshow", () => cerrar(enviando));

    // ------------------------------------------------------------------
    // Calendario en ventana emergente
    // ------------------------------------------------------------------
    const dialogoCalendario = document.getElementById("dialogo-calendario");
    const abrirCalendario = document.getElementById("abrir-calendario");
    const quitarHorario = document.getElementById("quitar-horario");
    const horarioElegido = document.getElementById("horario-elegido");
    const fecha = document.getElementById("id_fecha_propuesta");
    const tatuadora = document.getElementById("quote-artist");
    const formatoFecha = new Intl.DateTimeFormat("es-CL", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
    function hora() { return document.getElementById("id_hora_propuesta"); }

    function textoHorario() {
        if (!fecha || !fecha.value) return "";
        const f = formatoFecha.format(new Date(`${fecha.value}T12:00:00Z`));
        const h = hora() && hora().value ? ` · ${hora().value.slice(0, 5)}` : "";
        return f.charAt(0).toUpperCase() + f.slice(1) + h;
    }
    function actualizarHorario() {
        const t = textoHorario();
        horarioElegido.textContent = t ? `Tu preferencia: ${t}` : "";
        quitarHorario.hidden = !t;
        abrirCalendario.textContent = t ? "Cambiar horario" : "Ver horarios disponibles";
    }
    if (dialogoCalendario && window.FullCalendar) {
        document.getElementById("fecha-acciones").hidden = false;
        abrirCalendario.addEventListener("click", () => {
            if (!tatuadora.value) {
                ir(1);
                marcarError(tatuadora, "Elige primero con quién quieres tatuarte para ver su agenda.");
                tatuadora.tarjetas && tatuadora.tarjetas.querySelector(".opcion").focus();
                return;
            }
            abrir(dialogoCalendario);
            document.dispatchEvent(new CustomEvent("mt:calendario-abierto"));
        });
        document.addEventListener("mt:dia-elegido", () => {
            cerrar(dialogoCalendario);
            actualizarHorario();
            if (hora() && !hora().value) hora().focus();
            else abrirCalendario.focus();
        });
        document.getElementById("sin-horario").addEventListener("click", () => {
            cerrar(dialogoCalendario);
            setTimeout(actualizarHorario, 0);
        });
    }
    quitarHorario.addEventListener("click", () => {
        fecha.value = "";
        fecha.dispatchEvent(new Event("change", { bubbles: true }));
        actualizarHorario();
    });
    if (fecha) { fecha.addEventListener("change", actualizarHorario); }
    form.addEventListener("change", (e) => { if (e.target.id === "id_hora_propuesta") actualizarHorario(); });
    actualizarHorario();

    // ------------------------------------------------------------------
    // Resúmenes: en vivo (escritorio) y revisión final (todos)
    // ------------------------------------------------------------------
    const clp = new Intl.NumberFormat("es-CL");
    function textoDe(nombre) {
        const c = form.elements.namedItem(nombre);
        if (!c) return "";
        if (c.tagName === "SELECT") return c.value ? c.options[c.selectedIndex].textContent.trim() : "";
        if (c.type === "checkbox") return c.checked ? "Sí" : "";
        return (c.value || "").trim();
    }
    function datos() {
        const alto = textoDe("alto_cm"), ancho = textoDe("ancho_cm");
        const nombreCompleto = [textoDe("nombre"), textoDe("primer_apellido"), textoDe("segundo_apellido")].filter(Boolean).join(" ");
        const canalTexto = textoDe("canal_preferido");
        const social = textoDe("usuario_social");
        const monto = textoDe("presupuesto");
        const estilo = document.getElementById("analysis-result").hidden ? "" : document.getElementById("analysis-style").textContent;
        return [
            { paso: 1, titulo: "Tatuadora", valor: textoDe("tatuadora") },
            { paso: 1, titulo: "Zona", valor: textoDe("zona") },
            { paso: 1, titulo: "Tamaño", valor: alto && ancho ? `${alto} × ${ancho} cm` : "" },
            { paso: 1, titulo: "Color y detalle", valor: [textoDe("color"), textoDe("detalle")].filter(Boolean).join(" · ") },
            { paso: 1, titulo: "Cubrir un tatuaje", valor: textoDe("cobertura") },
            { paso: 1, titulo: "Tu idea", valor: textoDe("idea"), largo: true },
            { paso: 2, titulo: "Estilo sugerido", valor: estilo },
            { paso: 3, titulo: "Horario preferido", valor: textoHorario() || "Sin preferencia", siempre: true },
            { paso: 4, titulo: "Nombre", valor: nombreCompleto },
            { paso: 4, titulo: "Contacto", valor: [textoDe("email"), textoDe("telefono")].filter(Boolean).join(" · ") },
            { paso: 4, titulo: "Prefiere", valor: canalTexto + (social ? ` (${social})` : "") },
            { paso: 4, titulo: "Presupuesto", valor: monto ? `$${clp.format(Number(monto))} CLP` : "" },
        ];
    }
    function miniatura() {
        const p = document.getElementById("reference-preview");
        if (p.hidden || !p.getAttribute("src")) return null;
        const img = document.createElement("img");
        img.src = p.src; img.alt = "Tu referencia"; img.className = "resumen-imagen";
        return img;
    }
    function lista(conEditar) {
        const dl = document.createElement("dl");
        dl.className = "resumen-lista";
        for (const d of datos()) {
            if (!d.valor && !d.siempre) continue;
            const fila = document.createElement("div");
            fila.className = "resumen-fila" + (d.largo ? " resumen-larga" : "");
            const dt = document.createElement("dt"); dt.textContent = d.titulo;
            const dd = document.createElement("dd"); dd.textContent = d.valor;
            fila.append(dt, dd);
            if (conEditar) {
                const b = document.createElement("button");
                b.type = "button"; b.className = "text-button resumen-editar"; b.textContent = "Editar";
                b.setAttribute("aria-label", `Editar ${d.titulo.toLowerCase()}`);
                b.addEventListener("click", () => ir(d.paso));
                fila.append(b);
            }
            dl.append(fila);
        }
        return dl;
    }
    function construirRevision() {
        resumenRevision.replaceChildren();
        const img = miniatura();
        if (img) {
            const cab = document.createElement("div");
            cab.className = "resumen-cabecera";
            const editar = document.createElement("button");
            editar.type = "button"; editar.className = "text-button"; editar.textContent = "Cambiar imagen";
            editar.addEventListener("click", () => ir(2));
            cab.append(img, editar);
            resumenRevision.append(cab);
        }
        resumenRevision.append(lista(true));
        resumenRevision.hidden = false;
    }
    function actualizarResumenes() {
        if (!resumenVivo) return;
        const contenido = [];
        const img = miniatura();
        if (img) contenido.push(img);
        const dl = lista(false);
        if (dl.children.length > 1 || img) contenido.push(dl);
        resumenVivoContenido.replaceChildren(...contenido);
        // Solo cuando ya hay algo propio de la persona (no valores por defecto)
        const empezado = Boolean(form.elements.namedItem("tatuadora").value || img);
        resumenVivo.hidden = !empezado || actual === total || !document.getElementById("quote-summary").hidden;
        if (actual === total) construirRevision();
    }
    document.getElementById("reference-preview").addEventListener("load", actualizarResumenes);
    new MutationObserver(actualizarResumenes).observe(document.getElementById("analysis-result"), { attributes: true, childList: true, subtree: true });

    // ------------------------------------------------------------------
    // Arranque
    // ------------------------------------------------------------------
    form.classList.add("con-pasos");
    nav.hidden = false;
    acciones.hidden = false;
    // Con errores del servidor: abrir el primer paso que los tenga
    let inicial = 1;
    const primerError = form.querySelector(".con-error");
    if (primerError) inicial = Number(primerError.closest(".paso").dataset.paso);
    else if (document.getElementById("form-errors")) inicial = 2; // hay que volver a elegir la imagen
    maximoVisitado = document.getElementById("form-errors") ? total : inicial;
    history.replaceState({ paso: inicial, prof: 0 }, "", `#paso-${inicial}`);
    ir(inicial, { historial: false, enfocar: Boolean(primerError) });
    actualizarResumenes();
});

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function formulario(maximo = 10 * 1024 * 1024) {
  const cambios = {};
  let submit;
  const input = {
    id: "imagen", dataset: { maxBytes: String(maximo) }, files: [],
    form: { addEventListener: (evento, handler, captura) => { assert.equal(evento, "submit"); assert.equal(captura, true); submit = handler; } },
    after: (...elementos) => { input.mensajes = elementos; },
    getAttribute: () => null,
    setAttribute: () => {},
    setCustomValidity: (mensaje) => { input.validationMessage = mensaje; },
    addEventListener: (evento, handler) => { cambios[evento] = handler; },
    focus: () => { input.enfocado = true; },
    reportValidity: () => { input.aviso = true; },
  };
  const document = {
    querySelectorAll: () => [input],
    createElement: () => ({ setAttribute: () => {} }),
  };
  const archivo = path.join(__dirname, "../../config/static/js/peso-imagen.js");
  vm.runInNewContext(fs.readFileSync(archivo, "utf8"), { document });
  return {
    input,
    seleccionar: (size) => { input.files = [{ size }]; cambios.change(); },
    quitar: () => { input.files = []; cambios.input(); },
    enviar: () => {
      const evento = { preventDefault: () => { evento.bloqueado = true; }, stopImmediatePropagation: () => { evento.detenido = true; } };
      submit(evento);
      return evento;
    },
  };
}

test("10 MiB exactos se admiten y un byte adicional se bloquea antes del envío", () => {
  const f = formulario();
  f.seleccionar(10 * 1024 * 1024);
  assert.equal(f.input.validationMessage, "");
  assert.equal(f.enviar().bloqueado, undefined);
  f.seleccionar(10 * 1024 * 1024 + 1);
  assert.match(f.input.validationMessage, /supera/);
  assert.equal(f.input.mensajes[1].hidden, false);
  const envio = f.enviar();
  assert.equal(envio.bloqueado, true);
  assert.equal(envio.detenido, true);
  assert.equal(f.input.enfocado, true);
  assert.equal(f.input.aviso, true);
});

test("el límite recibido del servidor y el archivo vacío también se comprueban", () => {
  const f = formulario(2 * 1024 * 1024);
  f.seleccionar(3 * 1024 * 1024);
  assert.match(f.input.validationMessage, /máximo de 2 MB/);
  assert.equal(f.enviar().bloqueado, true);
  f.seleccionar(0);
  assert.match(f.input.validationMessage, /vacío/);
  f.quitar();
  assert.equal(f.input.validationMessage, "");
  assert.equal(f.input.mensajes[1].hidden, true);
});

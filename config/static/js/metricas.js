"use strict";
setInterval(async () => {
  if (document.hidden) return;
  try {
    const response = await fetch(location.href, {headers: {"Accept": "text/html"}, cache: "no-store"});
    if (!response.ok || response.redirected) return;
    const doc = new DOMParser().parseFromString(await response.text(), "text/html");
    const fresh = doc.getElementById("metricas-vivas");
    if (fresh) document.getElementById("metricas-vivas").replaceWith(fresh);
  } catch (_) { /* Keep the last confirmed snapshot when offline. */ }
}, 60000);

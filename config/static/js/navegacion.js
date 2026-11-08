"use strict";
document.addEventListener('DOMContentLoaded',()=>{
 const boton=document.getElementById('alternar-menu'),barra=document.getElementById('barra-lateral');
 if(!boton||!barra)return;
 let oculta=window.matchMedia('(max-width:850px)').matches;
 try {if(!oculta)oculta=localStorage.getItem('mtflow-menu-oculto')==='1';}catch(e){}
 function actualizar(){document.body.classList.toggle('menu-oculto',oculta);barra.hidden=oculta;boton.setAttribute('aria-expanded',String(!oculta));boton.setAttribute('aria-label',oculta?'Mostrar menú':'Ocultar menú');}
 boton.addEventListener('click',()=>{oculta=!oculta;actualizar();try{localStorage.setItem('mtflow-menu-oculto',oculta?'1':'0');}catch(e){}});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){document.querySelectorAll('.menu-cuenta[open]').forEach(m=>m.open=false);if(window.innerWidth<=850&&!oculta){oculta=true;actualizar();boton.focus();}}});
 document.addEventListener('click',e=>{document.querySelectorAll('.menu-cuenta[open]').forEach(m=>{if(!m.contains(e.target))m.open=false;});});
 actualizar();
});

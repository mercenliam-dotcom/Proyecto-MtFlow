from django.shortcuts import render
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from apps.clasificacion.catalogo import ESTILOS
from apps.clasificacion.cliente_ml import clasificar, ServicioMLNoDisponible
from apps.clasificacion.views import _miniatura_data_uri
from .forms import CotizacionForm
from .precios import estimar
from .limites import admitir_cotizacion

# IMPORTAMOS LOS NUEVOS MODELOS
from .models import Cliente, Tatuadora, Postulacion, Imagen, Estilo, Prediccion

# (Las funciones portafolio y horarios se mantienen idénticas)
def portafolio(request):
    descripciones = ["La fuerza del negro y el espacio", "Historias que se vuelven tinta", "Trazos orgánicos y digitales", "Palabras con identidad", "Sutileza en cada línea", "Ritmo, simetría y composición", "Formas que siguen el cuerpo"]
    trabajos = [{"estilo": nombre, "descripcion": descripcion} for nombre, descripcion in zip(
        (nombre for codigo, nombre in ESTILOS.items() if codigo != "E-99"), descripciones)]
    return render(request, "web/portafolio.html", {"trabajos": trabajos})

def horarios(request):
    return render(request, "web/horarios.html")

@never_cache
@require_http_methods(["GET", "POST"])
def cotizacion(request):
    contexto = {}
    estado = 200
    if request.method == "POST" and not admitir_cotizacion(request):
        contexto["limite"] = True
        form = CotizacionForm()
        estado = 429
    else:
        form = CotizacionForm(request.POST if request.method == "POST" else None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            datos = form.cleaned_data
            contenido = form.validada.archivo.read()
            
            # 1. GESTIÓN DEL CLIENTE (Buscamos si existe, si no, lo creamos)
            cliente_obj, created = Cliente.objects.get_or_create(
                correo=datos["email"],
                defaults={
                    "nombres": datos["nombre"],
                    "apellidos": "", 
                    "telefono": datos["telefono"]
                }
            )

            # 2. ASIGNACIÓN REAL DE TATUADORA
            tatuadora_obj = datos["tatuadora"]
            nombre_tatuadora_resumen = tatuadora_obj.nombre if tatuadora_obj else "Cualquiera de las dos"
            if not tatuadora_obj:
                tatuadora_obj = Tatuadora.objects.filter(activa=True).first()

            # 3. CÁLCULO DE ÁREA REAL Y DEFINICIÓN DE cat_tamano
            alto = float(datos["alto_cm"])
            ancho = float(datos["ancho_cm"])
            area_calculada = alto * ancho
            
            # Aquí definimos la variable antes de usarla
            if area_calculada <= 25: 
                cat_tamano = "pequeno"
            elif area_calculada <= 150: 
                cat_tamano = "mediano"
            elif area_calculada <= 625: 
                cat_tamano = "grande"
            else: 
                cat_tamano = "especial"

            # 4. CONSOLIDAR DESCRIPCIÓN Y CREAR POSTULACIÓN
            descripcion_completa = f"IDEA: {datos['idea']} | COLOR: {datos['color']} | DETALLE: {datos['detalle']} | COVER-UP: {datos['cobertura']}"
            
            datos["tamano"] = cat_tamano
            estimacion_precios = estimar(datos)
            
            postulacion_obj = Postulacion.objects.create(
                cliente=cliente_obj,
                tatuadora=tatuadora_obj,
                zona_cuerpo=datos["zona"],
                alto_cm=alto,
                ancho_cm=ancho,
                area_cm2=area_calculada,
                categoria_tamano=cat_tamano,
                descripcion=descripcion_completa,
                estado="RECIBIDA",
                precio_sugerido=estimacion_precios.get("minimo", 0)
            )

            # 5. GUARDAR REGISTRO DE IMAGEN
            imagen_obj = Imagen.objects.create(
                postulacion=postulacion_obj,
                url=f"temporal_local/{form.validada.archivo.name}", # Simulación de S3
                orden=1,
                es_principal=True,
                formato=form.validada.formato,
                ancho_px=800, 
                alto_px=800,
                tamano_bytes=len(contenido)
            )

            # CORRECCIÓN DE DICCIONARIO: Prevenimos KeyError al mostrar el resumen
            contexto.update(
                estimacion=estimacion_precios, 
                miniatura=_miniatura_data_uri(contenido),
                resumen={
                    "nombre": datos["nombre"], 
                    "email": datos["email"], 
                    "telefono": datos["telefono"],
                    "idea": datos["idea"], 
                    "tatuadora": nombre_tatuadora_resumen
                }
            )
            
            # 6. FLUJO DE MACHINE LEARNING
            if datos["analizar"]:
                try:
                    resultado = clasificar(contenido, form.validada.archivo.name,
                                           "image/jpeg" if form.validada.formato == "JPEG" else "image/png")
                    
                    # Guardamos la predicción en la BD
                    estilo_obj, _ = Estilo.objects.get_or_create(
                        codigo=resultado.estilo_sugerido, 
                        defaults={"nombre": ESTILOS.get(resultado.estilo_sugerido, "Desconocido")}
                    )
                    Prediccion.objects.create(
                        imagen=imagen_obj,
                        version_modelo=resultado.version_modelo,
                        estilo_sugerido=estilo_obj,
                        confianza_maxima=resultado.confianza_maxima,
                        tiempo_inferencia_ms=150 # Ficticio para el registro
                    )

                except ServicioMLNoDisponible:
                    contexto["error_ml"] = True
                else:
                    contexto["estilo"] = ESTILOS[resultado.estilo_sugerido]
                    contexto["simulado"] = resultado.version_modelo.startswith("simulado")
                    contexto["revision_ml"] = resultado.estilo_sugerido == "E-99" or resultado.confianza_maxima < settings.UMBRAL_REVISION
        elif request.method == "POST":
            estado = 400
    contexto["form"] = form
    respuesta = render(request, "web/cotizacion.html", contexto, status=estado)
    if estado == 429:
        respuesta["Retry-After"] = str(settings.COTIZACION_VENTANA_SEGUNDOS)
    return respuesta
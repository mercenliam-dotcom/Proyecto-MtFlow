from django.shortcuts import render


def portafolio(request):
    trabajos = [
        {"estilo": "Fine Line", "descripcion": "Trazos finos y delicados"},
        {"estilo": "Realismo", "descripcion": "Detalles y profundidad"},
        {"estilo": "Blackwork", "descripcion": "Contrastes en tinta negra"},
        {"estilo": "Floral", "descripcion": "Composiciones botánicas"},
        {"estilo": "Anime", "descripcion": "Personajes e ilustraciones"},
        {"estilo": "Dotwork", "descripcion": "Texturas mediante puntos"},
    ]

    return render(request, "web/portafolio.html", {"trabajos": trabajos})
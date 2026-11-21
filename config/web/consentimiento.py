"""Texto del consentimiento informado.

Una sola fuente para la página pública (/consentimiento/) y para la página
donde se firma: el cliente siempre firma exactamente lo que se publica.
Si el estudio cambia el texto, sube VERSION; cada firma guarda la versión que aceptó.

El texto es un modelo de referencia del rubro; el estudio debe revisarlo
(idealmente con asesoría legal) antes de usarlo con clientes reales.
"""

VERSION = "2026-11"

SECCIONES = [
    {
        "titulo": "Requisitos para tatuarte",
        "puntos": [
            "Debes ser mayor de 18 años y presentar tu cédula de identidad el día de la sesión.",
            "No tatuamos bajo los efectos del alcohol o de otras sustancias, ni sobre piel irritada, herida o con infección.",
            "Si estás embarazada o en período de lactancia, conversa primero con tu tatuadora: lo habitual es postergar la sesión.",
        ],
    },
    {
        "titulo": "Qué te preguntaremos antes de la sesión",
        "puntos": [
            "Fecha de nacimiento, para confirmar tu mayoría de edad.",
            "Alergias conocidas (tintas, látex, metales, anestésicos o productos de cuidado).",
            "Condiciones médicas relevantes: diabetes, problemas de coagulación, epilepsia, enfermedades del corazón o de la piel, entre otras.",
            "Medicamentos que tomas, en especial anticoagulantes o tratamientos para la piel.",
            "Si consumiste alcohol en las últimas 24 horas.",
        ],
        "nota": "Tus respuestas son datos de salud: solo las ve tu tatuadora y se usan para cuidar tu seguridad.",
    },
    {
        "titulo": "Riesgos que conviene conocer",
        "puntos": [
            "Molestias, enrojecimiento, inflamación leve y pequeñas costras durante los primeros días.",
            "Reacciones alérgicas a pigmentos, que pueden aparecer incluso tiempo después.",
            "Infección si no se siguen los cuidados indicados.",
            "El resultado final depende también de tu tipo de piel y de la cicatrización; un retoque puede ser necesario.",
            "Un tatuaje es permanente: borrarlo requiere tratamientos largos y no siempre completos.",
        ],
    },
    {
        "titulo": "Cuidados después de la sesión",
        "puntos": [
            "Sigue las indicaciones de limpieza e hidratación que te entregue tu tatuadora.",
            "Evita sol directo, piscinas, mar y saunas hasta que cicatrice.",
            "No rasques ni arranques las costras.",
            "Ante fiebre, dolor intenso o secreción, consulta a un profesional de la salud.",
        ],
    },
    {
        "titulo": "Fotografías y privacidad",
        "puntos": [
            "Solo publicamos fotos de tu tatuaje en el portafolio si lo autorizas expresamente; puedes negarte sin ningún efecto en tu atención.",
            "Tus datos de contacto y de salud no se publican ni se comparten con terceros.",
        ],
    },
    {
        "titulo": "Firma",
        "puntos": [
            "El día de la sesión, completarás la ficha con tu tatuadora y la firmarás escribiendo tu nombre completo.",
            "Tu tatuadora firma, por su parte, una declaración de higiene, uso de material estéril y explicación de los riesgos.",
            "Sin ambas firmas no se realiza la sesión.",
        ],
    },
]

# Lo que firma la tatuadora en su declaración (cada punto es una casilla obligatoria).
DECLARACION_TATUADORA = [
    ("higiene", "El espacio de trabajo y las superficies fueron limpiados y desinfectados antes de la sesión."),
    ("material", "Uso agujas y material desechable estériles, abiertos frente al cliente, y tintas dentro de su vencimiento."),
    ("riesgos", "Expliqué al cliente los riesgos y cuidados descritos en el consentimiento y respondí sus dudas."),
    ("ficha", "Revisé la ficha de salud del cliente y no encontré impedimentos para realizar el trabajo."),
]

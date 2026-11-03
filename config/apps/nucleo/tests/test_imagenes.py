"""
Pruebas de la validación de imágenes: lo permitido pasa, todo lo demás se rechaza.
Cada prueba corresponde a un ataque o error concreto.
"""
import io

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from PIL import Image

from apps.nucleo.imagenes import validar_imagen

from . import utilidades as u


class ImagenesPermitidas(SimpleTestCase):
    def test_jpg_valido(self):
        r = validar_imagen(u.jpg_valido())
        self.assertEqual(r.formato, "JPEG")
        self.assertEqual((r.ancho_px, r.alto_px), (400, 300))
        self.assertTrue(r.archivo.name.endswith(".jpg"))

    def test_jpeg_con_extension_jpeg_y_mayusculas(self):
        self.assertEqual(validar_imagen(u.jpg_valido("FOTO.JPEG")).formato, "JPEG")

    def test_png_valido(self):
        self.assertEqual(validar_imagen(u.png_valido()).formato, "PNG")

    def test_png_con_transparencia(self):
        self.assertEqual(validar_imagen(u.png_valido(modo="RGBA")).formato, "PNG")

    def test_nombre_guardado_es_aleatorio(self):
        r = validar_imagen(u.jpg_valido("../../etc/passwd.jpg"))
        self.assertNotIn("passwd", r.archivo.name)
        self.assertNotIn("/", r.archivo.name)
        self.assertEqual(len(r.archivo.name), 32 + 4)

    def test_elimina_metadatos_exif(self):
        exif = Image.Exif()
        exif[0x010F] = "CamaraDelCliente"          # fabricante
        exif[0x013B] = "Nombre Del Cliente"         # autor
        exif.get_ifd(0x8825)[2] = (33.0, 27.0, 0.0)  # latitud GPS
        original = u.imagen_bytes(exif=exif.tobytes())
        self.assertIn(b"CamaraDelCliente", original)  # el original sí los tiene
        r = validar_imagen(u.subido("a.jpg", original))
        limpia = Image.open(io.BytesIO(r.archivo.read()))
        self.assertEqual(len(limpia.getexif()), 0)

    def test_elimina_contenido_politoglota(self):
        # JPEG real con un script pegado al final: la re-codificación lo descarta
        datos = u.imagen_bytes("JPEG") + b"<script>alert(1)</script>"
        r = validar_imagen(u.subido("x.jpg", datos))
        self.assertNotIn(b"<script>", r.archivo.read())


class FormatosRechazados(SimpleTestCase):
    def assertRechaza(self, archivo, codigo):
        with self.assertRaises(ValidationError) as ctx:
            validar_imagen(archivo)
        self.assertEqual(ctx.exception.code, codigo, ctx.exception.messages)
        return ctx.exception

    def test_gif(self):
        self.assertRechaza(u.subido("a.gif", u.gif_bytes(), "image/gif"), "extension")

    def test_gif_renombrado_jpg(self):
        e = self.assertRechaza(u.subido("a.jpg", u.gif_bytes()), "firma")
        self.assertIn("GIF", e.messages[0])

    def test_webp_renombrado_png(self):
        self.assertRechaza(u.subido("a.png", u.webp_bytes(), "image/png"), "firma")

    def test_png_animado_apng(self):
        self.assertRechaza(u.subido("a.png", u.png_animado(), "image/png"), "animada")

    def test_svg_con_script(self):
        self.assertRechaza(u.subido("a.svg", u.SVG_CON_SCRIPT, "image/svg+xml"), "extension")

    def test_svg_renombrado_png(self):
        self.assertRechaza(u.subido("a.png", u.SVG_CON_SCRIPT, "image/png"), "firma")

    def test_html_renombrado_jpg(self):
        self.assertRechaza(u.subido("a.jpg", u.HTML_CON_SCRIPT), "firma")


class DocumentosYVideosRechazados(SimpleTestCase):
    def assertRechaza(self, archivo, codigo="firma"):
        with self.assertRaises(ValidationError) as ctx:
            validar_imagen(archivo)
        self.assertEqual(ctx.exception.code, codigo, ctx.exception.messages)
        return ctx.exception

    def test_pdf(self):
        self.assertRechaza(u.subido("doc.pdf", u.PDF_FALSO, "application/pdf"), "extension")

    def test_pdf_renombrado_jpg(self):
        e = self.assertRechaza(u.subido("doc.jpg", u.PDF_FALSO))
        self.assertIn("PDF", e.messages[0])

    def test_word_renombrado_png(self):
        self.assertRechaza(u.subido("doc.png", u.DOCX_FALSO, "image/png"))

    def test_mp4(self):
        self.assertRechaza(u.subido("video.mp4", u.MP4_FALSO, "video/mp4"), "extension")

    def test_mp4_renombrado_jpg_con_content_type_mentiroso(self):
        e = self.assertRechaza(u.subido("video.jpg", u.MP4_FALSO, "image/jpeg"))
        self.assertIn("video", e.messages[0])

    def test_mov_renombrado_png(self):
        self.assertRechaza(u.subido("clip.png", u.MOV_FALSO, "image/png"))

    def test_webm_renombrado_jpg(self):
        self.assertRechaza(u.subido("clip.jpg", u.WEBM_FALSO))

    def test_doble_extension(self):
        self.assertRechaza(u.subido("foto.jpg.exe", u.imagen_bytes()), "extension")

    def test_extension_no_calza_con_contenido(self):
        # PNG real con nombre .jpg
        self.assertRechaza(u.subido("a.jpg", u.imagen_bytes("PNG")), "extension_falsa")


class LimitesYCalidad(SimpleTestCase):
    def assertRechaza(self, archivo, codigo):
        with self.assertRaises(ValidationError) as ctx:
            validar_imagen(archivo)
        self.assertEqual(ctx.exception.code, codigo, ctx.exception.messages)

    def test_archivo_vacio(self):
        self.assertRechaza(u.subido("a.jpg", b""), "vacio")

    @override_settings(IMAGEN_MAX_BYTES=50_000)
    def test_demasiado_pesada(self):
        self.assertRechaza(u.jpg_valido(tamano=(800, 800)), "tamano")

    def test_demasiado_pequena(self):
        self.assertRechaza(u.jpg_valido(tamano=(100, 300)), "pequena")

    @override_settings(IMAGEN_LADO_MAX_PX=500)
    def test_demasiado_grande(self):
        self.assertRechaza(u.jpg_valido(tamano=(600, 300)), "grande")

    @override_settings(IMAGEN_MAX_PIXELES=50_000)
    def test_bomba_de_descompresion(self):
        self.assertRechaza(u.jpg_valido(tamano=(400, 300)), "bomba")

    def test_borrosa(self):
        self.assertRechaza(u.jpg_valido(nitida=False), "borrosa")

    def test_jpeg_truncado(self):
        datos = u.imagen_bytes("JPEG")[:3000]
        self.assertRechaza(u.subido("a.jpg", datos), "corrupta")

    def test_png_truncado(self):
        datos = u.imagen_bytes("PNG")[:500]
        self.assertRechaza(u.subido("a.png", datos, "image/png"), "corrupta")

    def test_nombre_con_caracteres_de_control(self):
        self.assertRechaza(u.subido("a\x00.jpg", u.imagen_bytes()), "nombre")

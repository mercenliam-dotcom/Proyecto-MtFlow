from datetime import timedelta
from tempfile import TemporaryDirectory
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .test_recepcion import profesional, propuesta
from .forms import CotizacionForm
from .models import Estilo
from apps.nucleo.forms_agenda import BloqueForm
from apps.nucleo.tests.utilidades import jpg_valido


class AjustesEquipo(TestCase):
    def setUp(self):
        self.a = profesional()
        self.client.force_login(self.a.usuario)

    def test_redes_opcionales_presupuesto_omitido_analisis_forzado(self):
        d = propuesta(self.a, canal_preferido='instagram', analizar='', presupuesto=100)
        f = CotizacionForm(d, {'imagen':d.pop('imagen')})
        self.assertTrue(f.is_valid(), f.errors)
        self.assertTrue(f.cleaned_data['analizar'])
        self.assertNotIn('presupuesto', f.cleaned_data)
        self.assertEqual(f.cleaned_data['canal_preferido'], 'correo')

    def test_fecha_chilena_validaciones_y_calendario_al_reservar(self):
        dia=timezone.localdate()+timedelta(days=2)
        d={'tipo':'BLOQUEO','fecha':dia.strftime('%d/%m/%Y'),'hora_inicio':'10:00','hora_fin':'11:00'}
        f=BloqueForm(d,tatuadora=self.a)
        self.assertTrue(f.is_valid(),f.errors)
        self.assertEqual(f.cleaned_data['fecha'],dia)
        d['fecha']='31/02/2027'
        self.assertFalse(BloqueForm(d,tatuadora=self.a).is_valid())
        r=self.client.get(reverse('nucleo:agenda_nuevo'),{'fecha':dia.isoformat()})
        self.assertContains(r,dia.strftime('%d/%m/%Y'))
        self.assertContains(r,'data-mode="reserva"')
        self.assertIn("'nonce-",r['Content-Security-Policy'])

    def test_foto_publicada_aparece_en_galeria_filtrable_y_no_borradores(self):
        with TemporaryDirectory() as carpeta, self.settings(MEDIA_ROOT=carpeta):
            estilo=Estilo.objects.first()
            r=self.client.post(reverse('nucleo:portafolio_nuevo'),{'titulo':'Obra publicada','tipo':'TATUAJE','estilo':estilo.pk,'imagen':jpg_valido(),'visible':'on','autorizacion_publicacion':'on','en_carrusel':'on'})
            self.assertEqual(r.status_code,302)
            self.client.post(reverse('nucleo:portafolio_nuevo'),{'titulo':'Obra privada','tipo':'TATUAJE','estilo':estilo.pk,'imagen':jpg_valido()})
            r=Client().get(reverse('web:portafolio'))
            self.assertContains(r,f'data-style="{estilo.nombre}"')
            self.assertContains(r,'Obra publicada')  # destacada en el carrusel
            self.assertNotContains(r,'Obra privada')
            grupo=next(g for g in r.context['grupos'] if g['nombre']==estilo.nombre)
            self.assertEqual(grupo['cantidad'],1)
            r=Client().get(reverse('web:catalogo'),{'estilo':grupo['slug']})
            self.assertContains(r,'Obra publicada')
            self.assertNotContains(r,'Obra privada')

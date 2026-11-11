import time
from unittest.mock import patch, Mock
from urllib.parse import urlparse, parse_qs
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core.cache import cache
from django.http import HttpResponseRedirect
from authlib.integrations.base_client.errors import OAuthError
from apps.cuentas import social
from apps.cuentas.models import Usuario, IdentidadSocial
from .test_clientes import cliente
from web.test_recepcion import profesional

CONFIG = dict(ACCESO_SOCIAL_VISIBLE=True, GOOGLE_CLIENT_ID='client-test', GOOGLE_CLIENT_SECRET='secret-test', FACEBOOK_CLIENT_ID='fb-test', FACEBOOK_CLIENT_SECRET='fb-secret-test', FACEBOOK_API_VERSION='v24.0', SOCIAL_AUTH_BASE_URL='https://estudio.example.test')


@override_settings(**CONFIG)
class AccesoSocial(TestCase):
    def setUp(self):
        cache.clear()
        self.u = cliente()
        self.inicio = reverse('cuentas:social_iniciar',args=['google'])
        self.callback = reverse('cuentas:social_callback',args=['google'])
        self.datos = dict(proveedor='google',identificador='google-123',email='nuevo@example.test',nombre='María',apellido='Soto')

    def flujo(self, proveedor='google', usuario=None, hora=None):
        s=self.client.session
        s['social_flujo']={'proveedor':proveedor,'hora':hora or time.time(),'usuario':usuario.pk if usuario else None,'firma':usuario.get_session_auth_hash() if usuario else None}
        s.save()

    def responder(self, datos=None):
        with patch('apps.cuentas.social.identidad',return_value=datos or self.datos):
            return self.client.get(self.callback,{'code':'codigo','state':'estado'})

    def test_sin_configuracion_no_ofrece_botones_ni_inicia(self):
        with self.settings(GOOGLE_CLIENT_ID='',FACEBOOK_CLIENT_ID=''):
            self.assertNotContains(self.client.get(reverse('cuentas:login')),'Continuar con Google')
            self.assertEqual(self.client.post(self.inicio).status_code,404)

    def test_iniciar_exige_post_csrf_y_no_expone_secretos(self):
        self.assertEqual(self.client.get(self.inicio).status_code,405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.inicio).status_code,403)
        r=self.client.get(reverse('cuentas:login'))
        self.assertContains(r,'Continuar con Google');self.assertContains(r,'Continuar con Facebook')
        self.assertNotContains(r,'secret-test')

    def test_google_autorizacion_real_tiene_state_nonce_pkce_y_callback_fijo(self):
        metadata={'authorization_endpoint':'https://accounts.google.com/o/oauth2/v2/auth','token_endpoint':'https://oauth2.googleapis.com/token','issuer':'https://accounts.google.com'}
        with patch('authlib.integrations.django_client.apps.DjangoOAuth2App.load_server_metadata',return_value=metadata):
            r=self.client.post(self.inicio)
        q=parse_qs(urlparse(r['Location']).query)
        for k in ('state','nonce','code_challenge'): self.assertTrue(q[k][0])
        self.assertEqual(q['redirect_uri'],['https://estudio.example.test'+self.callback])
        self.assertNotIn('client_secret',q)

    def test_callback_sin_flujo_o_vencido_no_contacta_proveedor(self):
        with patch('apps.cuentas.social.identidad') as identidad:
            self.client.get(self.callback)
            self.flujo(hora=time.time()-601);self.client.get(self.callback)
            identidad.assert_not_called()
        self.assertNotIn('_auth_user_id',self.client.session)

    def test_state_invalido_se_rechaza_con_authlib_sin_login(self):
        self.flujo()
        with patch('requests.sessions.Session.request') as red:
            self.client.get(self.callback,{'code':'falso','state':'falso'})
            red.assert_not_called()
        self.assertNotIn('_auth_user_id',self.client.session)

    def test_identidad_google_requiere_token_y_email_verificado(self):
        oauth=Mock()
        for token in ({'userinfo':{'sub':'123','email_verified':True}}, {'id_token':'token','userinfo':{'sub':'123','email_verified':False}}):
            oauth.authorize_access_token.return_value=token
            with self.assertRaises(ValueError): social.identidad(oauth,Mock(),'google')

    def test_facebook_usa_id_y_no_guarda_token(self):
        oauth=Mock();oauth.authorize_access_token.return_value={'access_token':'token-privado'}
        oauth.get.return_value.json.return_value={'id':'fb123','first_name':'Ana','last_name':'Soto'}
        d=social.identidad(oauth,Mock(),'facebook')
        self.assertEqual(d['identificador'],'fb123');self.assertNotIn('token-privado',str(d))
        self.assertIn('appsecret_proof',oauth.get.call_args.kwargs['params'])

    def test_google_verifica_firma_nonce_audiencia_y_vencimiento(self):
        from joserfc import jwt
        from joserfc.jwk import RSAKey
        from joserfc.errors import JoseError
        clave=RSAKey.generate_key(2048)
        otra=RSAKey.generate_key(2048)
        cliente=social.cliente_oauth('google')
        claims={'iss':'https://accounts.google.com','aud':'client-test','sub':'google-123','nonce':'nonce-correcto','iat':int(time.time()),'exp':int(time.time())+300,'email_verified':True,'email':'nuevo@example.test'}
        metadata={'issuer':'https://accounts.google.com','id_token_signing_alg_values_supported':['RS256']}
        with patch.object(cliente,'load_server_metadata',return_value=metadata), patch.object(cliente,'fetch_jwk_set',return_value={'keys':[clave.as_dict(private=False)]}):
            token={'id_token':jwt.encode({'alg':'RS256'},claims,clave)}
            self.assertEqual(cliente.parse_id_token(token,nonce='nonce-correcto')['sub'],'google-123')
            for cambio, llave in [({'nonce':'otro'},clave),({'aud':'otro-cliente'},clave),({'exp':int(time.time())-1000},clave),({'iss':'https://falso.example'},clave),({},otra)]:
                token={'id_token':jwt.encode({'alg':'RS256'},{**claims,**cambio},llave)}
                with self.assertRaises(JoseError): cliente.parse_id_token(token,nonce='nonce-correcto')

    def test_correo_existente_no_vincula_ni_inicia_sesion(self):
        self.flujo();self.responder({**self.datos,'email':self.u.email})
        self.assertFalse(IdentidadSocial.objects.exists())
        self.assertNotIn('_auth_user_id',self.client.session)
        self.assertNotIn('social_pendiente',self.client.session)

    def test_alta_crea_solo_cliente_y_password_respaldo(self):
        self.flujo();self.assertRedirects(self.responder(),reverse('cuentas:social_completar'))
        r=self.client.post(reverse('cuentas:social_completar'),{'nombre_usuario':'nuevocliente','nombre':'María','apellido':'Soto','email':'inyectado@example.test','password1':'Respaldo2026Seguro','password2':'Respaldo2026Seguro','rol':'ADMIN','es_tatuadora':'on'})
        self.assertRedirects(r,reverse('clientes:inicio'))
        u=Usuario.objects.get(nombre_usuario='nuevocliente')
        self.assertEqual(u.email,'nuevo@example.test');self.assertEqual(u.rol,'USUARIO');self.assertFalse(u.es_tatuadora)
        self.assertFalse(u.is_superuser);self.assertFalse(u.debe_cambiar_contrasena)
        self.assertTrue(u.check_password('Respaldo2026Seguro'))
        self.assertEqual(IdentidadSocial.objects.get().usuario,u)
        self.assertNotIn('social_pendiente',self.client.session)

    def test_vincular_exige_clave_y_no_modifica_rol(self):
        self.client.force_login(self.u)
        with patch('apps.cuentas.social.cliente_oauth') as oauth:
            self.client.post(self.inicio,{'accion':'vincular','actual':'incorrecta'})
            oauth.return_value.authorize_redirect.assert_not_called()
            oauth.return_value.authorize_redirect.return_value=HttpResponseRedirect('https://accounts.google.com/')
            self.client.post(self.inicio,{'accion':'vincular','actual':'Clave2026PersonalSegura'})
        self.responder()
        self.assertEqual(IdentidadSocial.objects.get().usuario,self.u)
        self.u.refresh_from_db();self.assertEqual(self.u.rol,'USUARIO')

    def test_no_roba_identidad_de_otra_cuenta_y_sesion_cambiada(self):
        otra=cliente('cliente2');IdentidadSocial.objects.create(usuario=otra,proveedor='google',identificador='google-123')
        self.client.force_login(self.u);self.flujo(usuario=self.u);self.responder()
        self.assertEqual(IdentidadSocial.objects.get().usuario,otra)
        self.flujo(usuario=otra)
        with patch('apps.cuentas.social.identidad') as proveedor:
            self.client.get(self.callback);proveedor.assert_not_called()

    def test_login_vinculado_y_cuenta_desactivada(self):
        IdentidadSocial.objects.create(usuario=self.u,proveedor='google',identificador='google-123')
        self.flujo();self.responder();self.assertEqual(int(self.client.session['_auth_user_id']),self.u.pk)
        self.client.logout();self.u.is_active=False;self.u.save()
        self.flujo();self.responder();self.assertNotIn('_auth_user_id',self.client.session)

    def test_desvincular_solo_propias_y_con_password(self):
        IdentidadSocial.objects.create(usuario=self.u,proveedor='google',identificador='google-123')
        self.client.force_login(self.u);url=reverse('cuentas:social_conexiones')
        self.client.post(url,{'proveedor':'google','actual':'incorrecta'});self.assertEqual(IdentidadSocial.objects.count(),1)
        self.client.post(url,{'proveedor':'google','actual':'Clave2026PersonalSegura'});self.assertFalse(IdentidadSocial.objects.exists())
        self.assertTrue(Usuario.objects.filter(pk=self.u.pk).exists())

    def test_cancelacion_no_expone_error_del_proveedor(self):
        self.flujo()
        with patch('apps.cuentas.social.identidad',side_effect=OAuthError(description='secreto-no-mostrar')):
            r=self.client.get(self.callback,follow=True)
        self.assertNotContains(r,'secreto-no-mostrar')
        self.assertNotIn('_auth_user_id',self.client.session)

    def test_credenciales_no_habilitan_origen_http_en_produccion(self):
        with self.settings(DEBUG=False,SOCIAL_AUTH_BASE_URL='http://example.com'):
            self.assertEqual(social.disponibles(),[])

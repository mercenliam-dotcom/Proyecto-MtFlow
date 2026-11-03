"""Límite durante lectura multipart, antes de escribir el archivo completo a disco."""
from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.core.files.uploadhandler import FileUploadHandler


class LimiteImagenUploadHandler(FileUploadHandler):
    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.recibidos = 0

    def receive_data_chunk(self, raw_data, start):
        self.recibidos += len(raw_data)
        if self.recibidos > settings.IMAGEN_MAX_BYTES:
            raise RequestDataTooBig("La imagen supera el tamaño permitido.")
        return raw_data

    def file_complete(self, file_size):
        return None

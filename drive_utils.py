import os
from PyQt5.QtCore import QThread, pyqtSignal


class UploadWorker(QThread):
    """Hilo en segundo plano para subir archivos a Google Drive."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, tipo, factura, titular, archivos):
        super().__init__()
        self.tipo = tipo
        self.factura = factura
        self.titular = titular
        self.archivos = archivos

    def run(self):
        """Ejecuta la subida de archivos en segundo plano."""
        try:
            from pydrive.auth import GoogleAuth
            from pydrive.drive import GoogleDrive

            gauth = GoogleAuth()
            gauth.LocalWebserverAuth()
            drive = GoogleDrive(gauth)

            carpeta_drive = self.obtener_o_crear_carpeta(drive)

            for archivo in self.archivos:
                nombre_archivo = os.path.basename(archivo)
                f = drive.CreateFile({
                    'title': nombre_archivo,
                    'parents': [{'id': carpeta_drive['id']}]
                })
                f.SetContentFile(archivo)
                f.Upload()

            self.finished.emit("Archivos subidos correctamente a Google Drive.")

        except Exception as e:
            self.error.emit(f"Error en la subida: {e}")

    def obtener_o_crear_carpeta(self, drive):
        """Busca o crea la carpeta de destino en Google Drive."""
        nombre_carpeta = f"{self.tipo}_{self.factura}_{self.titular}"
        query = f"title='{nombre_carpeta}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        lista = drive.ListFile({'q': query}).GetList()

        if lista:
            return lista[0]

        carpeta = drive.CreateFile({'title': nombre_carpeta,
                                    'mimeType': 'application/vnd.google-apps.folder'})
        carpeta.Upload()
        return carpeta

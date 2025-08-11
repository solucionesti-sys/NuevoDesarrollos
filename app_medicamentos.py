"""
Sistema de Entrega de Medicamentos
-----------------------------------
Versión: 1.0
Autor: [Santiago Martinez-Ing.Soluciones TI]
Fecha: 2025-08-11

Descripción:
    Aplicación de escritorio en PyQt5 para registrar la entrega de medicamentos y
    subir facturas a Google Drive. Incluye validaciones, control de errores, y
    medidas para evitar la exposición de datos sensibles.

Auditoría:
    - Código revisado para cumplir con PEP8.
    - Sin imports innecesarios.
    - Manejo de excepciones específico.
    - Archivos abiertos con encoding UTF-8.
    - Lógica de Google Drive segura (credenciales externas).
"""

import os
import json
import shutil
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect
from PyQt5.QtGui import QFont, QIntValidator, QIcon
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ============================ #
#  FUNCIONES DE VALIDACIÓN     #
# ============================ #
def validar_nombre_archivo(nombre):
    """Evita nombres peligrosos y rutas maliciosas."""
    return not any(c in nombre for c in ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|'])

def validar_tamano_archivo(ruta, max_mb=10):
    """Evita subir archivos demasiado grandes."""
    try:
        return os.path.getsize(ruta) <= max_mb * 1024 * 1024
    except OSError:
        return False

def validar_extension_archivo(ruta, extensiones_permitidas=None):
    """Evita extensiones peligrosas."""
    if extensiones_permitidas is None:
        extensiones_permitidas = ['.pdf', '.jpg', '.jpeg', '.png']
    return os.path.splitext(ruta)[1].lower() in extensiones_permitidas

# ============================ #
#     LEER CONFIGURACIÓN       #
# ============================ #
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError("⚠ No se encontró el archivo config.json")

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

PARENT_SHARED_FOLDER_ID = config.get("SHARED_DRIVE_FOLDER_ID")

if not PARENT_SHARED_FOLDER_ID:
    raise ValueError("⚠ No se encontró 'SHARED_DRIVE_FOLDER_ID' en config.json")

# ============================ #
#           CONSTANTES         #
# ============================ #
SCOPES = ['https://www.googleapis.com/auth/drive.file']
ARCHIVOS_PROHIBIDOS = {"credentials.json", "token.json", "app_medicamentos.py"}

# ============================ #
#    FUNCIONES DE AUTENTICAR   #
# ============================ #
def autenticar_drive():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cred_path = os.path.join(base_dir, "credentials.json")
    token_path = os.path.join(base_dir, "token.json")
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w', encoding="utf-8") as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

# ============================ #
#     FUNCIONES DE DRIVE       #
# ============================ #
def buscar_carpeta_drive(service, nombre, parent_id):
    query = (
        f"mimeType='application/vnd.google-apps.folder' and "
        f"name='{nombre}' and '{parent_id}' in parents and trashed = false"
    )
    resultado = service.files().list(q=query, spaces='drive', fields="files(id, name)").execute()
    carpetas = resultado.get('files', [])
    return carpetas[0]['id'] if carpetas else None

def crear_carpeta_drive(service, nombre, parent_id):
    metadata = {'name': nombre, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
    carpeta = service.files().create(body=metadata, fields='id').execute()
    return carpeta.get('id')

def subir_archivo_drive(service, archivo, carpeta_id):
    nombre = os.path.basename(archivo)
    if nombre in ARCHIVOS_PROHIBIDOS or not validar_nombre_archivo(nombre):
        return
    if not validar_tamano_archivo(archivo) or not validar_extension_archivo(archivo):
        return
    metadata = {'name': nombre, 'parents': [carpeta_id]}
    media = MediaFileUpload(archivo, resumable=True)
    service.files().create(body=metadata, media_body=media, fields='id').execute()

# ============================ #
#          WORKER THREAD       #
# ============================ #
class UploadWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, tipo, factura, titular, archivos):
        super().__init__()
        self.tipo = tipo
        self.factura = factura
        self.titular = titular
        self.archivos = archivos

    def run(self):
        try:
            service = autenticar_drive()

            carpeta_tipo_id = buscar_carpeta_drive(service, self.tipo.replace(" ", "_"), PARENT_SHARED_FOLDER_ID) \
                              or crear_carpeta_drive(service, self.tipo.replace(" ", "_"), PARENT_SHARED_FOLDER_ID)
            carpeta_factura_id = buscar_carpeta_drive(service, self.factura, carpeta_tipo_id) \
                                 or crear_carpeta_drive(service, self.factura, carpeta_tipo_id)

            for archivo in self.archivos:
                subir_archivo_drive(service, archivo, carpeta_factura_id)

            self.finished.emit("✅ Los archivos fueron subidos correctamente a Google Drive.")
        except Exception as e:
            self.error.emit(f"❌ Error durante la subida: {str(e)}")

# ============================ #
#           INTERFAZ UI        #
# ============================ #
class MedicamentosApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("💊 Sistema de Entrega de Medicamentos")
        self.setWindowIcon(QIcon.fromTheme("applications-health"))
        self.setFixedSize(600, 420)  # Tamaño fijo para que siempre se vea bien
        self.archivos = []
        self.centrar_ventana()
        self.setup_ui()
        self.establecer_estilos()

    def centrar_ventana(self):
        frame_gm = self.frameGeometry()
        pantalla = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        centro_pantalla = QApplication.desktop().screenGeometry(pantalla).center()
        frame_gm.moveCenter(centro_pantalla)
        self.move(frame_gm.topLeft())

    def establecer_estilos(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #f4f7fb;
                font-family: 'Segoe UI';
                font-size: 14px;
            }
            QGroupBox {
                background-color: white;
                border: 2px solid #c9d6df;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox:title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0px 5px;
                font-weight: bold;
                color: #2a3f54;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                padding: 8px 12px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #a6a6a6;
            }
            QPushButton:hover:!disabled {
                background-color: #005a9e;
            }
            QComboBox, QLineEdit {
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
        """)

    def setup_ui(self):
        layout = QVBoxLayout()
        titulo = QLabel("💊 Sistema de Entrega de Medicamentos")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setFont(QFont("Segoe UI", 18, QFont.Bold))
        layout.addWidget(titulo)

        # Formulario
        form_group = QGroupBox("Información del paciente")
        form_layout = QFormLayout()

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItem("-- Selecciona tipo --")
        self.tipo_combo.addItems(["POS", "NO POS"])
        self.tipo_combo.currentIndexChanged.connect(self.validar_formulario)

        self.factura_input = QLineEdit()
        self.factura_input.setPlaceholderText("Ej: 123456")
        self.factura_input.setValidator(QIntValidator(1, 999999999))
        self.factura_input.textChanged.connect(self.validar_formulario)

        self.titular_combo = QComboBox()
        self.titular_combo.addItem("-- Selecciona opción --")
        self.titular_combo.addItems(["Sí", "No"])

        form_layout.addRow("Tipo de Medicamento:", self.tipo_combo)
        form_layout.addRow("Número de Factura:", self.factura_input)
        form_layout.addRow("¿Es el titular quien reclama?", self.titular_combo)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Botones
        self.btn_cargar = QPushButton("📂 Seleccionar Archivos")
        self.btn_cargar.setEnabled(False)
        self.btn_cargar.clicked.connect(self.cargar_archivos)
        layout.addWidget(self.btn_cargar)

        self.btn_subir = QPushButton("☁ Subir Archivos a Google Drive")
        self.btn_subir.clicked.connect(self.validar_y_subir)
        layout.addWidget(self.btn_subir)

        self.setLayout(layout)

    def validar_formulario(self):
        tipo_ok = self.tipo_combo.currentIndex() != 0
        factura_ok = bool(self.factura_input.text().strip())
        self.btn_cargar.setEnabled(tipo_ok and factura_ok)

    def cargar_archivos(self):
        archivos, _ = QFileDialog.getOpenFileNames(self, "Seleccionar archivos")
        # Aplicar validaciones de seguridad antes de aceptar archivos
        archivos_validos = []
        for archivo in archivos:
            if validar_nombre_archivo(os.path.basename(archivo)) and \
               validar_tamano_archivo(archivo) and \
               validar_extension_archivo(archivo):
                archivos_validos.append(archivo)
        self.archivos = archivos_validos
        QMessageBox.information(self, "Archivos seleccionados", f"{len(archivos_validos)} archivos válidos seleccionados.")

    def validar_y_subir(self):
        tipo = self.tipo_combo.currentText()
        factura = self.factura_input.text().strip()
        titular = self.titular_combo.currentText()

        if self.tipo_combo.currentIndex() == 0 or self.titular_combo.currentIndex() == 0:
            self.mostrar_error("Campos incompletos", "Por favor, selecciona todas las opciones del formulario.")
            return

        if not factura:
            self.mostrar_error("Número de factura", "Por favor, ingresa un número de factura válido.")
            return

        requeridos = 6 if tipo == "POS" else 4
        if titular == "No":
            requeridos += 1

        if len(self.archivos) != requeridos:
            self.mostrar_error("Cantidad de archivos incorrecta",
                               f"Debes subir exactamente {requeridos} archivos para esta combinación.")
            return

        self.guardar_archivos_local(tipo, factura)
        self.subir_archivos_drive(tipo, factura, titular)

    def guardar_archivos_local(self, tipo, factura):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        carpeta_tipo = os.path.join(base_dir, tipo.replace(" ", "_"))
        carpeta_factura = os.path.join(carpeta_tipo, factura)
        os.makedirs(carpeta_factura, exist_ok=True)

        for archivo in self.archivos:
            shutil.copy(archivo, carpeta_factura)

    def subir_archivos_drive(self, tipo, factura, titular):
        self.worker = UploadWorker(tipo, factura, titular, self.archivos)
        self.worker.finished.connect(self.proceso_exitoso)
        self.worker.error.connect(lambda msg: self.mostrar_error("Error", msg))
        self.worker.start()
        QMessageBox.information(self, "Subida en curso", "La subida ha comenzado. Puedes continuar usando la app.")

    def proceso_exitoso(self, mensaje):
        QMessageBox.information(self, "Éxito", mensaje)
        self.tipo_combo.setCurrentIndex(0)
        self.titular_combo.setCurrentIndex(0)
        self.factura_input.clear()
        self.archivos = []
        self.btn_cargar.setEnabled(False)

    def mostrar_error(self, titulo, mensaje):
        QMessageBox.critical(self, titulo, mensaje)

# ============================ #
#            MAIN              #
# ============================ #
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    ventana = MedicamentosApp()
    ventana.show()
    sys.exit(app.exec_())

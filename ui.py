import os
import shutil
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox, QComboBox,
    QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIntValidator, QIcon

from drive_utils import UploadWorker
from validations import validar_formulario


class MedicamentosApp(QWidget):
    """Ventana principal del sistema de entrega de medicamentos."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("💊 Sistema de Entrega de Medicamentos")
        self.setWindowIcon(QIcon.fromTheme("applications-health"))
        self.setFixedSize(600, 420)
        self.archivos = []
        self.centrar_ventana()
        self.setup_ui()
        self.establecer_estilos()

    def centrar_ventana(self):
        """Centrar la ventana en la pantalla."""
        frame_gm = self.frameGeometry()
        pantalla = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        centro_pantalla = QApplication.desktop().screenGeometry(pantalla).center()
        frame_gm.moveCenter(centro_pantalla)
        self.move(frame_gm.topLeft())

    def establecer_estilos(self):
        """Aplicar estilos visuales."""
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
        """Crear elementos de la interfaz."""
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
        form_layout.addRow("¿Es el titular quien reclama?:", self.titular_combo)

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
        """Habilitar botón de cargar archivos si hay datos completos."""
        tipo_ok = self.tipo_combo.currentIndex() != 0
        factura_ok = bool(self.factura_input.text().strip())
        self.btn_cargar.setEnabled(tipo_ok and factura_ok)

    def cargar_archivos(self):
        """Abrir explorador de archivos para seleccionar documentos."""
        archivos, _ = QFileDialog.getOpenFileNames(self, "Seleccionar archivos")
        self.archivos = archivos
        QMessageBox.information(self, "Archivos seleccionados", f"{len(archivos)} archivos seleccionados.")

    def validar_y_subir(self):
        """Validar campos y subir archivos a Google Drive."""
        tipo = self.tipo_combo.currentText()
        factura = self.factura_input.text().strip()
        titular = self.titular_combo.currentText()

        if not validar_formulario(tipo, factura, titular, len(self.archivos)):
            self.mostrar_error("Error", "Validación fallida. Verifica los campos.")
            return

        self.guardar_archivos_local(tipo, factura)
        self.subir_archivos_drive(tipo, factura, titular)

    def guardar_archivos_local(self, tipo, factura):
        """Guardar copia local de archivos."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        carpeta_tipo = os.path.join(base_dir, tipo.replace(" ", "_"))
        carpeta_factura = os.path.join(carpeta_tipo, factura)
        os.makedirs(carpeta_factura, exist_ok=True)

        for archivo in self.archivos:
            shutil.copy(archivo, carpeta_factura)

    def subir_archivos_drive(self, tipo, factura, titular):
        """Iniciar subida de archivos en segundo plano."""
        self.worker = UploadWorker(tipo, factura, titular, self.archivos)
        self.worker.finished.connect(self.proceso_exitoso)
        self.worker.error.connect(lambda msg: self.mostrar_error("Error", msg))
        self.worker.start()
        QMessageBox.information(self, "Subida en curso", "La subida ha comenzado. Puedes continuar usando la app.")

    def proceso_exitoso(self, mensaje):
        """Reiniciar formulario tras subida exitosa."""
        QMessageBox.information(self, "Éxito", mensaje)
        self.tipo_combo.setCurrentIndex(0)
        self.titular_combo.setCurrentIndex(0)
        self.factura_input.clear()
        self.archivos = []
        self.btn_cargar.setEnabled(False)

    def mostrar_error(self, titulo, mensaje):
        """Mostrar mensaje de error."""
        QMessageBox.critical(self, titulo, mensaje)

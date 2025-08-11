from PyQt5.QtWidgets import QApplication
from ui import MedicamentosApp
import sys


def main():
    """Punto de entrada de la aplicación."""
    app = QApplication(sys.argv)
    ventana = MedicamentosApp()
    ventana.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

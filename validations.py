import os


def validar_formulario(tipo, factura, titular, cantidad_archivos):
    """Valida que todos los campos estén completos y correctos."""
    if tipo not in ["POS", "NO POS"]:
        return False
    if not factura.isdigit():
        return False
    if titular not in ["Sí", "No"]:
        return False
    if cantidad_archivos == 0:
        return False
    return True


def validar_nombre_archivo(nombre):
    """Evita nombres con caracteres peligrosos."""
    return all(c.isalnum() or c in " ._-()" for c in nombre)


def validar_tamano_archivo(ruta, max_mb=10):
    """Valida que el archivo no exceda un tamaño máximo en MB."""
    return os.path.getsize(ruta) <= max_mb * 1024 * 1024


def validar_extension_archivo(nombre, extensiones_permitidas=None):
    """Valida que la extensión esté permitida."""
    if extensiones_permitidas is None:
        extensiones_permitidas = [".pdf", ".jpg", ".png"]
    _, ext = os.path.splitext(nombre)
    return ext.lower() in extensiones_permitidas

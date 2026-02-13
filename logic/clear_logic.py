import os
import shutil
import json
from datetime import datetime
from config import DOWNLOAD_FOLDERS

# Ruta para almacenar los resultados JSON de las tareas asíncronas
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

def truncar_log():
    """Vacía el contenido del archivo de log sin eliminarlo."""
    log_path = "logs/log.txt"
    if os.path.exists(log_path):
        with open(log_path, 'w', encoding='utf-8') as f:
            f.truncate(0)
    return True

def limpiar_archivos_temporales(portal=None, tipo=None, fecha_filtro=None):
    """
    Elimina archivos en DOWNLOAD_FOLDERS según filtros de portal, tipo y fecha.
    fecha_filtro puede ser DD/MM/YYYY, MM/YYYY o YYYY.
    """
    conteo_eliminados = 0
    
    # Mapeo de carpetas basado en config.py
    for clave, ruta in DOWNLOAD_FOLDERS.items():
        # Filtro por portal (ENDESA o ENEL)
        if portal and portal.upper() not in clave:
            continue
        # Filtro por tipo (PDF, XML, CSV)
        if tipo and tipo.upper() not in clave:
            continue
            
        if os.path.exists(ruta):
            for archivo in os.listdir(ruta):
                ruta_completa = os.path.join(ruta, archivo)
                if os.path.isfile(ruta_completa):
                    # Lógica de filtro por fecha de creación
                    mtime = os.path.getmtime(ruta_completa)
                    dt_archivo = datetime.fromtimestamp(mtime)
                    
                    borrar = True
                    if fecha_filtro:
                        partes = fecha_filtro.split('/')
                        if len(partes) == 3: # DD/MM/YYYY
                            borrar = dt_archivo.strftime('%d/%m/%Y') == fecha_filtro
                        elif len(partes) == 2: # MM/YYYY
                            borrar = dt_archivo.strftime('%m/%Y') == fecha_filtro
                        elif len(partes) == 1: # YYYY
                            borrar = dt_archivo.strftime('%Y') == fecha_filtro
                    
                    if borrar:
                        os.remove(ruta_completa)
                        conteo_eliminados += 1
                        
    return conteo_eliminados

def guardar_resultado_tarea(task_id, datos):
    """Guarda el listado de facturas en un archivo JSON físico."""
    ruta_resultado = os.path.join(RESULTS_DIR, f"{task_id}.json")
    with open(ruta_resultado, 'w', encoding='utf-8') as f:
        # Convertimos objetos Pydantic a dict si es necesario
        json_datos = [d.dict() if hasattr(d, 'dict') else d for d in datos]
        json.dump(json_datos, f, ensure_ascii=False, indent=4)
    return ruta_resultado

def obtener_resultado_tarea(task_id):
    """Lee el resultado JSON de una tarea terminada."""
    ruta_resultado = os.path.join(RESULTS_DIR, f"{task_id}.json")
    if os.path.exists(ruta_resultado):
        with open(ruta_resultado, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None
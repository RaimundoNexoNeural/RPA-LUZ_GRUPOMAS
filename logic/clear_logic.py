import os
import re
from datetime import datetime, timedelta
from config import DOWNLOAD_FOLDERS
from parsers.exportar_datos import (
    borrar_registros_procesados,
    borrar_registros_enviadas,
)

# === MANTENIMIENTO Y LIMPIEZA DE RECURSOS === 

# A. Ruta para almacenar los resultados JSON de las tareas asíncronas
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)


# CLR.1 Gestion de logs: truncado y retención

def truncar_log(nivel: str | None = None, retencion_dias: int = 15) -> dict:
    """
    Limpia los archivos de la carpeta `logs`.

    - Si `nivel` se especifica (DEBUG/INFO/WARNING/ERROR/CRITICAL), sólo afecta a
      esa categoría. En caso contrario actúa sobre todos los niveles.
    - Los archivos activos (<nivel>.txt) se truncarán si existen.
    - Los históricos (<nivel>.YYYY-MM-DD.txt) con fecha anterior a la retención se
      eliminan.

    Retorna un diccionario con conteos: {'truncados': n_activos, 'eliminados_historicos': n_historicos}
    """
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    niveles_validos = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if nivel and nivel not in niveles_validos:
        raise ValueError(f"Nivel de log inválido: {nivel}")

    # permitimos dos estilos de rotación:
    #  - "<nivel>.YYYY-MM-DD.txt" (especificación nueva)
    #  - "<nivel>.txt.YYYY-MM-DD.txt" (nombre que genera el handler actual)
    patrones = []
    if nivel:
        patrones.append(
            re.compile(
                rf"^{nivel}(?:\.txt)?(?:\.(\d{{4}}-\d{{2}}-\d{{2}}))?\.txt$"
            )
        )
    else:
        patrones = [
            re.compile(
                rf"^{lvl}(?:\.txt)?(?:\.(\d{{4}}-\d{{2}}-\d{{2}}))?\.txt$"
            )
            for lvl in niveles_validos
        ]

    truncados = 0
    eliminados = 0
    ahora = datetime.now()
    umbral = ahora - timedelta(days=retencion_dias)

    for fname in os.listdir(log_dir):
        fpath = os.path.join(log_dir, fname)
        if not os.path.isfile(fpath):
            continue

        for pat in patrones:
            m = pat.match(fname)
            if not m:
                continue

            fecha_str = m.group(1)
            # archivo activo (sin fecha)
            if fecha_str is None:
                # truncar
                try:
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.truncate(0)
                    truncados += 1
                except Exception:
                    pass
            else:
                # histórico: comprobar antigüedad
                try:
                    fecha = datetime.strptime(fecha_str, "%Y-%m-%d")
                    if fecha < umbral:
                        os.remove(fpath)
                        eliminados += 1
                except Exception:
                    # si el parseo falla, ignorar
                    pass
            break  # patrón encontrado, no probar con otros

    return {"truncados": truncados, "eliminados_historicos": eliminados}


# CLR.2 Borrado selectivo de archivos temporales


# CLR.2 Borrado selectivo de archivos temporales
def limpiar_archivos_temporales(portal=None, tipo=None, fecha_filtro=None):
    '''
    Elimina archivos de las carpetas de descarga aplicando filtros opcionales de origen, formato y fecha.
    Parametros:
        - portal (str): Filtro por distribuidora ("ENDESA" o "ENEL").
        - tipo (str): Filtro por extensión o categoría ("PDF", "XML", "CSV").
        - fecha_filtro (str): Fecha de creación en formatos "DD/MM/YYYY", "MM/YYYY" o "YYYY".
    Retorna
        - int: Número total de archivos eliminados durante el proceso.
    '''
    conteo_eliminados = 0
    
    # A. Iteración sobre el mapeo de carpetas configurado en config.py
    for clave, ruta in DOWNLOAD_FOLDERS.items():
        
        # A.1. Aplicación de filtro por portal (Origen de los datos)
        if portal and portal.upper() not in clave:
            continue
            
        # A.2. Aplicación de filtro por tipo (Formato de archivo)
        if tipo and tipo.upper() not in clave:
            continue
            
        # B. Procesamiento de la ruta física si existe
        if os.path.exists(ruta):
            for archivo in os.listdir(ruta):
                ruta_completa = os.path.join(ruta, archivo)
                
                if os.path.isfile(ruta_completa):
                    # B.1. Obtención de metadatos de tiempo del archivo
                    mtime = os.path.getmtime(ruta_completa)
                    dt_archivo = datetime.fromtimestamp(mtime)
                    
                    # B.2. Evaluación de criterios de borrado
                    borrar = True
                    if fecha_filtro:
                        partes = fecha_filtro.split('/')
                        
                        # B.2.1. Filtro por día exacto (DD/MM/YYYY)
                        if len(partes) == 3:
                            borrar = dt_archivo.strftime('%d/%m/%Y') == fecha_filtro
                        # B.2.2. Filtro por mes y año (MM/YYYY)
                        elif len(partes) == 2:
                            borrar = dt_archivo.strftime('%m/%Y') == fecha_filtro
                        # B.2.3. Filtro por año (YYYY)
                        elif len(partes) == 1:
                            borrar = dt_archivo.strftime('%Y') == fecha_filtro
                    
                    # C. Ejecución de la eliminación física
                    if borrar:
                        os.remove(ruta_completa)
                        conteo_eliminados += 1
                        
    return conteo_eliminados
# CLR.3 Eliminaci�n de registros de facturas procesadas

def limpiar_registros_procesados(portal: str | None = None) -> int:
    """
    Borra los ficheros CSV que contienen el registro de facturas ya procesadas.
    - `portal` puede ser "ENDESA" o "ENEL" (no sensible a may�sculas); si se
      omite se eliminan ambos.
    Retorna el n�mero de ficheros eliminados.
    """
    clave = portal.lower() if portal else None
    cont = borrar_registros_procesados(clave)  # funci�n importada del parser
    return cont


# CLR.4 Eliminaci�n de registros de facturas enviadas por email

def limpiar_registros_enviadas(portal: str | None = None) -> int:
    """
    Id�ntico a `limpiar_registros_procesados` pero act�a sobre los hist�ricos de
    env�os.
    """
    clave = portal.lower() if portal else None
    cont = borrar_registros_enviadas(clave)
    return cont

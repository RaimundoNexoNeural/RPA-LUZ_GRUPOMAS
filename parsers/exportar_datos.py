import csv
import os
from logic.logs_logic import log, mail_handler

# === 1. REGISTRO DE FACTURAS PROCESADAS === 
    
    # A. Caché de facturas procesadas para optimizar lecturas
_registros_cache_procesadas: dict[str, dict[tuple[str,str], str]] = {}


# PROC.1 Obtención de rutas por distribuidora
def _get_path_procesados(distribuidora: str) -> str:
    '''
    Devuelve la ruta del CSV de procesados para una distribuidora concreta.
    Parametros:
        - distribuidora (str): Identificador de la distribuidora ("endesa" o "enel")
    Retorna:
        - str: Ruta completa del archivo CSV de registros de proceso
    '''
    # A. Importación local para evitar dependencias circulares
    from config import REGISTRO_FOLDERS_PROCESADAS
    key = distribuidora.lower()
    
    # B. Validación de la existencia de la distribuidora en configuración
    if key not in REGISTRO_FOLDERS_PROCESADAS:
        log.error(f"Se intentó acceder a una distribuidora desconocida: {distribuidora}")
        raise ValueError(f"Distribuidora desconocida: {distribuidora}")
    
    # C. Construcción de la ruta del archivo de registro
    return os.path.join(REGISTRO_FOLDERS_PROCESADAS[key], f"procesados_{key}.csv")


# PROC.2 Carga de registros con sistema de caché
def cargar_registro_procesados(distribuidora: str) -> dict[tuple[str,str], str]:
    '''
    Carga en memoria el mapa de facturas procesadas asociadas a su marca de tiempo.
    Parametros:
        - distribuidora (str): Nombre de la distribuidora a consultar
    Retorna:
        - dict[tuple[str,str], str]: Diccionario con clave (CUP, número_factura) y valor timestamp
    '''
    # A. Verificación de existencia en caché para evitar E/S innecesaria
    key = distribuidora.lower()
    if key in _registros_cache_procesadas:
        log.debug(f"Cargando registros procesados de '{key}' desde caché")
        return _registros_cache_procesadas[key]

    # B. Inicialización y carga desde el archivo físico si no está en caché
    path = _get_path_procesados(key)
    registros: dict[tuple[str,str], str] = {}
    
    if os.path.isfile(path):
        log.debug(f"Leyendo archivo de registros procesados: {path}")
        try:
            # B.1. Lectura del CSV y mapeo de datos identificativos
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    cup = row.get('CUP', '').strip()
                    numero = row.get('numero_factura', '').strip()
                    fecha = row.get('fecha_hora', '').strip()
                    if cup and numero:
                        registros[(cup, numero)] = fecha
        except Exception as e:
            log.error(f"Error leyendo archivo de registros {path}: {e}")
            pass
    else:
        log.debug(f"No existe archivo de registros previo para '{key}' en {path}")

    # C. Actualización de caché y retorno
    _registros_cache_procesadas[key] = registros
    return registros


# PROC.3 Verificación de estado de procesamiento
def es_factura_procesada(distribuidora: str, cup: str, numero: str) -> str | None:
    """
    Verifica si una factura ya ha sido registrada como procesada anteriormente.
    Parametros:
        - distribuidora (str): Distribuidora de la factura
        - cup (str): Código CUP de suministro
        - numero (str): Número identificativo de la factura
    Retorna:
        - str | None: Fecha/hora de proceso si existe y no se fuerza reprocesamiento; None en caso contrario
    """
    # A. Verificación del flag de reprocesamiento global
    from config import REPROCESADO
    if REPROCESADO:
        return None
    
    # B. Consulta del registro cargado
    registros = cargar_registro_procesados(distribuidora)
    res = registros.get((cup, numero))
    if res:
        log.debug(f"Factura {numero} ya consta como procesada el {res}")
    return res


# PROC.4 Registro persistente de factura procesada
def registrar_factura_procesada(distribuidora: str, cup: str, numero: str) -> None:
    """
    Registra o actualiza una factura en el historial de procesamiento.
    Parametros:
        - distribuidora (str): Distribuidora origen
        - cup (str): Código CUP
        - numero (str): Número de factura
    Retorna:
        - None
    """
    # A. Preparación de datos y timestamp actual
    from config import REPROCESADO
    key = distribuidora.lower()
    registros = cargar_registro_procesados(key)
    fecha_hora = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # B. Gestión de facturas ya existentes en el registro
    if (cup, numero) in registros:
        # B.1. Si se requiere reprocesamiento, se actualiza el timestamp físico
        if REPROCESADO:
            log.debug(f"Actualizando marca de tiempo por reprocesado: {numero}")
            _actualizar_registro_procesados(key, cup, numero, fecha_hora)
            registros[(cup, numero)] = fecha_hora
        return
    
    # C. Adición de registro para facturas nuevas
    path = _get_path_procesados(key)
    file_exists = os.path.isfile(path)
    try:
        log.debug(f"Registrando nueva factura procesada en CSV: {numero}")
        with open(path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            # C.1. Inserción de cabecera si el archivo es de nueva creación
            if not file_exists:
                writer.writerow(['CUP', 'numero_factura', 'fecha_hora'])
            writer.writerow([cup, numero, fecha_hora])
    except Exception as e:
        log.error(f"Error al escribir en el registro de procesados {path}: {e}")
        pass
    
    # D. Actualización de la caché en memoria
    registros[(cup, numero)] = fecha_hora


# PROC.5 Actualización física del archivo de registros
def _actualizar_registro_procesados(distribuidora_key: str, cup: str, numero: str, nueva_fecha_hora: str) -> None:
    """
    Actualiza la marca de tiempo de una fila específica mediante reescritura del archivo.
    Parametros:
        - distribuidora_key (str): Identificador de la distribuidora
        - cup (str): CUP a localizar
        - numero (str): Número de factura a localizar
        - nueva_fecha_hora (str): Nuevo timestamp a registrar
    Retorna:
        - None
    """
    # A. Verificación de existencia del archivo
    path = _get_path_procesados(distribuidora_key)
    if not os.path.isfile(path):
        return
    
    registros_modificados = []
    try:
        # B. Lectura completa y actualización de la fila coincidente
        with open(path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                if row.get('CUP', '').strip() == cup and row.get('numero_factura', '').strip() == numero:
                    row['fecha_hora'] = nueva_fecha_hora
                registros_modificados.append(row)
        
        # C. Reescritura del archivo físico con los datos actualizados
        log.debug(f"Reescribiendo archivo de registros para actualizar fila: {numero}")
        with open(path, 'w', newline='', encoding='utf-8') as f:
            if registros_modificados:
                writer = csv.DictWriter(f, fieldnames=['CUP', 'numero_factura', 'fecha_hora'], delimiter=';')
                writer.writeheader()
                writer.writerows(registros_modificados)
        
        # D. Invalidación de caché para asegurar consistencia en futuras lecturas
        if distribuidora_key in _registros_cache_procesadas:
            del _registros_cache_procesadas[distribuidora_key]
    except Exception as e:
        log.error(f"Fallo crítico actualizando registro físico {path}: {e}")
        pass


# === 2. REGISTRO DE ENVÍOS POR EMAIL === 

    # A. Caché de facturas enviadas
_registros_cache_enviadas: dict[str, dict[tuple[str,str], str]] = {}


# MAIL.1 Obtención de rutas de envío por distribuidora
def _get_path_enviadas(distribuidora: str) -> str:
    """
    Devuelve la ruta del CSV de facturas enviadas.
    Parametros:
        - distribuidora (str): Nombre de la distribuidora
    Retorna:
        - str: Ruta al archivo de registros de envío
    """
    from config import REGISTRO_FOLDERS_ENVIADAS
    key = distribuidora.lower()
    if key not in REGISTRO_FOLDERS_ENVIADAS:
        log.error(f"Ruta de envíos no configurada para: {distribuidora}")
        raise ValueError(f"Distribuidora desconocida: {distribuidora}")
    return os.path.join(REGISTRO_FOLDERS_ENVIADAS[key], f"enviadas_{key}.csv")


# MAIL.2 Carga de registros de envío en caché
def cargar_registro_enviadas(distribuidora: str) -> dict[tuple[str,str], str]:
    """
    Carga en memoria el historial de envíos realizados.
    Parametros:
        - distribuidora (str): Distribuidora a consultar
    Retorna:
        - dict[tuple[str,str], str]: Mapa de envíos registrados
    """
    # A. Gestión de caché para optimización
    key = distribuidora.lower()
    if key in _registros_cache_enviadas:
        log.debug(f"Cargando historial de envíos '{key}' desde caché")
        return _registros_cache_enviadas[key]

    # B. Carga desde archivo físico
    path = _get_path_enviadas(key)
    registros: dict[tuple[str,str], str] = {}
    
    if os.path.isfile(path):
        log.debug(f"Leyendo historial de envíos: {path}")
        try:
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    cup = row.get('CUP', '').strip()
                    numero = row.get('numero_factura', '').strip()
                    fecha = row.get('fecha_hora', '').strip()
                    if cup and numero:
                        registros[(cup, numero)] = fecha
        except Exception as e:
            log.error(f"Error al leer historial de envíos {path}: {e}")
            pass

    # C. Persistencia en caché y retorno
    _registros_cache_enviadas[key] = registros
    return registros


# MAIL.3 Verificación de estado de envío
def es_factura_enviada(distribuidora: str, cup: str, numero: str) -> str | None:
    """
    Comprueba si una factura específica ya ha sido enviada por email.
    Parametros:
        - distribuidora (str): Distribuidora origen
        - cup (str): CUP de suministro
        - numero (str): Número de factura
    Retorna:
        - str | None: Timestamp de envío si existe; None en caso contrario
    """
    registros = cargar_registro_enviadas(distribuidora)
    res = registros.get((cup, numero))
    if res:
        log.debug(f"Factura {numero} ya fue enviada el {res}")
    return res


# MAIL.4 Registro de envío satisfactorio
def registrar_factura_enviada(distribuidora: str, cup: str, numero: str) -> None:
    """
    Registra una nueva entrada en el historial de envíos por email.
    Parametros:
        - distribuidora (str): Distribuidora origen
        - cup (str): CUP asociado
        - numero (str): Número de factura
    Retorna:
        - None
    """
    # A. Preparación y verificación de duplicados
    key = distribuidora.lower()
    registros = cargar_registro_enviadas(key)
    fecha_hora = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if (cup, numero) in registros:
        return

    # B. Registro persistente en el archivo CSV de envíos
    path = _get_path_enviadas(key)
    file_exists = os.path.isfile(path)
    try:
        log.debug(f"Registrando envío de factura en CSV: {numero}")
        with open(path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            if not file_exists:
                writer.writerow(['CUP', 'numero_factura', 'fecha_hora'])
            writer.writerow([cup, numero, fecha_hora])
    except Exception as e:
        log.error(f"Fallo al escribir registro de envío en {path}: {e}")
        pass
    
    # C. Actualización de caché
    registros[(cup, numero)] = fecha_hora


# === 3. UTILIDADES DE LIMPIEZA DE REGISTROS === 


# CLEAN.1 Vaciado de cachés internas (uso interno)
def _vaciar_cache_procesadas():
    """Borra la memoria caché de facturas procesadas (usado tras eliminación física)."""
    log.debug("Memoria caché de facturas procesadas vaciada.")
    _registros_cache_procesadas.clear()

def _vaciar_cache_enviadas():
    """Borra la memoria caché de facturas enviadas (usado tras eliminación física)."""
    log.debug("Memoria caché de facturas enviadas vaciada.")
    _registros_cache_enviadas.clear()


# CLEAN.2 Eliminación de archivos de registros procesados

def borrar_registros_procesados(distribuidora: str | None = None) -> int:
    """
    Elimina físicamente los CSV de facturas procesadas. Si se indica una
    distribuidora concreta ("endesa" o "enel"), solo actúa sobre ella;
    de lo contrario borra ambos.
    Devuelve el número de ficheros eliminados.
    """
    cont = 0
    distribuidoras = [distribuidora] if distribuidora else ["endesa", "enel"]
    for d in distribuidoras:
        try:
            path = _get_path_procesados(d)
        except ValueError:
            continue
        if os.path.isfile(path):
            try:
                log.debug(f"Eliminando archivo de registro físico: {path}")
                os.remove(path)
                cont += 1
            except Exception as e:
                log.error(f"No se pudo eliminar el archivo {path}: {e}")
                pass
    # invalidar caches
    _vaciar_cache_procesadas()
    return cont


# CLEAN.3 Eliminación de archivos de registros enviadas

def borrar_registros_enviadas(distribuidora: str | None = None) -> int:
    """
    Elimina físicamente los CSV de facturas enviadas por email. El comportamiento
    de filtro es idéntico a `borrar_registros_procesados`.
    """
    cont = 0
    distribuidoras = [distribuidora] if distribuidora else ["endesa", "enel"]
    for d in distribuidoras:
        try:
            path = _get_path_enviadas(d)
        except ValueError:
            continue
        if os.path.isfile(path):
            try:
                log.debug(f"Eliminando archivo de registro de envíos: {path}")
                os.remove(path)
                cont += 1
            except Exception as e:
                log.error(f"No se pudo eliminar el archivo de envíos {path}: {e}")
                pass
    # invalidar caches
    _vaciar_cache_enviadas()
    return cont


# === 4. EXPORTACIÓN DE RESULTADOS FINALES === 

# OUT.1 Inserción de datos de factura en CSV maestro
def insertar_factura_en_csv(factura, filepath: str):
    """
    Escribe los datos completos de un objeto factura en un archivo CSV de resultados.
    Parametros:
        - factura (Pydantic Model): Objeto factura (Endesa o Enel) con los datos procesados
        - filepath (str): Ruta al archivo CSV de salida
    Retorna:
        - None
    """
    try:
        # A. Extracción de datos del modelo Pydantic
        datos_fila = factura.model_dump()
        fieldnames = list(datos_fila.keys())
        
        # B. Verificación de existencia para gestión de cabeceras
        file_exists = os.path.isfile(filepath)

        # C. Escritura de fila en modo 'append'
        log.debug(f"Escribiendo datos de factura {factura.numero_factura} en CSV maestro: {filepath}")
        with open(filepath, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(datos_fila)
            
    except Exception as e:
        log.error(f"Error crítico al insertar línea en CSV maestro {filepath}: {e}")
        print(f"Error al insertar línea en CSV: {e}")
    """
    Inserta una única factura como una nueva fila en el CSV.
    Si el archivo no existe, escribe primero la cabecera.
    """
    try:
        # Extraemos los datos usando el método de Pydantic
        datos_fila = factura.model_dump()
        fieldnames = list(datos_fila.keys())
        
        # Comprobar si el archivo ya existe para decidir si poner cabecera
        file_exists = os.path.isfile(filepath)

        with open(filepath, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(datos_fila)
            
    except Exception as e:
        log.error(f"Error al insertar línea en CSV: {e}")
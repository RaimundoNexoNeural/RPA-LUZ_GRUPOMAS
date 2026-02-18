import csv
import os

# ------------------------------------------------------------------
# funcionalidad adicional: registros de facturas ya procesadas
# ------------------------------------------------------------------
# el cache ahora almacena un diccionario map[(cup,numero)] -> fecha_hora
_registros_cache: dict[str, dict[tuple[str,str], str]] = {}


def _get_path_procesados(distribuidora: str) -> str:
    """Devuelve la ruta del CSV de procesados para la distribuidora."""
    from config import REGISTRO_FOLDERS
    key = distribuidora.lower()
    if key not in REGISTRO_FOLDERS:
        raise ValueError(f"Distribuidora desconocida: {distribuidora}")
    return os.path.join(REGISTRO_FOLDERS[key], f"procesados_{key}.csv")


def cargar_registro_procesados(distribuidora: str) -> dict[tuple[str,str], str]:
    """Carga en memoria el mapa de facturas procesadas a su fecha/hora.

    El formato devuelto es {(cup, numero): fecha_hora}
    Usa un caché para no leer el fichero varias veces en la misma ejecución.
    """
    key = distribuidora.lower()
    if key in _registros_cache:
        return _registros_cache[key]

    path = _get_path_procesados(key)
    registros: dict[tuple[str,str], str] = {}
    if os.path.isfile(path):
        try:
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    cup = row.get('CUP', '').strip()
                    numero = row.get('numero_factura', '').strip()
                    fecha = row.get('fecha_hora', '').strip()
                    if cup and numero:
                        registros[(cup, numero)] = fecha
        except Exception:
            # si hay fallo al leer, dejamos el diccionario vacío
            pass

    _registros_cache[key] = registros
    return registros


def es_factura_procesada(distribuidora: str, cup: str, numero: str) -> str | None:
    """Verifica si una factura ya ha sido procesada.

    Devuelve:
    - str (fecha/hora): Si REPROCESADO=False y la factura está registrada.
    - None: Si la factura no existe en el registro, O si REPROCESADO=True
             (fuerza reprocesamiento ignorando registros anteriores).
    
    Lógica:
    - Si REPROCESADO=True: SIEMPRE retorna None (fuerza procesamiento).
    - Si REPROCESADO=False: consulta el registro y retorna fecha si existe.
    """
    from config import REPROCESADO
    if REPROCESADO:
        return None
    registros = cargar_registro_procesados(distribuidora)
    return registros.get((cup, numero))


def registrar_factura_procesada(distribuidora: str, cup: str, numero: str) -> None:
    """Registra o actualiza una factura procesada en el CSV.

    CASOS DE USO:
    1. Factura NUEVA (nunca procesada):
       - SIEMPRE crea una nueva línea en el registro con timestamp actual,
         independientemente de REPROCESADO.
    
    2. Factura YA PROCESADA:
       - Si REPROCESADO=False: NO hace nada (mantiene timestamp original).
       - Si REPROCESADO=True: ACTUALIZA el timestamp con la fecha/hora actual.
    """
    from config import REPROCESADO
    key = distribuidora.lower()
    registros = cargar_registro_procesados(key)
    fecha_hora = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # CASO 2a: Factura ya procesada y REPROCESADO=True -> actualizar timestamp
    if REPROCESADO and (cup, numero) in registros:
        _actualizar_registro_procesados(key, cup, numero, fecha_hora)
        registros[(cup, numero)] = fecha_hora
        return
    
    # CASO 2b: Factura ya procesada y REPROCESADO=False -> no hacer nada
    if (cup, numero) in registros:
        return

    # CASO 1: Factura nueva (no existe) -> crear nueva línea en el registro
    path = _get_path_procesados(key)
    file_exists = os.path.isfile(path)
    try:
        with open(path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            if not file_exists:
                writer.writerow(['CUP', 'numero_factura', 'fecha_hora'])
            writer.writerow([cup, numero, fecha_hora])
    except Exception:
        pass
    registros[(cup, numero)] = fecha_hora


def _actualizar_registro_procesados(distribuidora_key: str, cup: str, numero: str, nueva_fecha_hora: str) -> None:
    """Actualiza la fecha/hora de una factura existente en el CSV.

    Lee todo el fichero, localiza la fila correspondiente (CUP, numero),
    actualiza su timestamp, y reescribe el fichero completo.
    Invalida el caché tras la actualización.
    """
    path = _get_path_procesados(distribuidora_key)
    if not os.path.isfile(path):
        return
    
    registros = []
    try:
        # Leer todo el fichero
        with open(path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                if row.get('CUP', '').strip() == cup and row.get('numero_factura', '').strip() == numero:
                    # Actualizar la fila encontrada
                    row['fecha_hora'] = nueva_fecha_hora
                registros.append(row)
        
        # Reescribir el fichero completo
        with open(path, 'w', newline='', encoding='utf-8') as f:
            if registros:
                writer = csv.DictWriter(f, fieldnames=['CUP', 'numero_factura', 'fecha_hora'], delimiter=';')
                writer.writeheader()
                writer.writerows(registros)
        
        # Invalidar caché para que se recargue en la próxima lectura
        if distribuidora_key in _registros_cache:
            del _registros_cache[distribuidora_key]
    except Exception:
        pass


# ------------------------------------------------------------------
# funcionalidad original: exportar una factura cualquiera a CSV
# ------------------------------------------------------------------

def insertar_factura_en_csv(factura, filepath: str):
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
        print(f"Error al insertar línea en CSV: {e}")
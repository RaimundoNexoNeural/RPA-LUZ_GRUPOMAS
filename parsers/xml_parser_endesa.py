import re
from datetime import datetime

from logs import escribir_log
from modelos_datos import FacturaEndesa

# --------------------------------------------------------------------------------
# --- FUNCIONES AUXILIARES PARA LECTURA POR REGEX ---
# --------------------------------------------------------------------------------

RE_FLAG = re.DOTALL     # Usamos re.DOTALL (re.S) para que el punto coincida con saltos de línea

def _clean_text(text: str) -> str:
    """
    Limpia el texto, eliminando los prefijos de Namespace de las etiquetas XML.
    Busca patrones como <ns0:Tag o </ns0:Tag y los deja como <Tag o </Tag 
    """

    text = re.sub(r'<([/]?)\w+:', r'<\1', text)
    return text


def _extract_simple_value(file_content: str, tag_name: str, is_float: bool = False, is_date: bool = False,default=None):
    """
    Extrae la primera ocurrencia de un valor basado en su etiqueta (ignorando Namespaces).
    Patrón: 
        <TagNombre>(Valor)</TagNombre>
    """

    pattern = r"<" + re.escape(tag_name) + r">([\s\S]*?)</" + re.escape(tag_name) + r">"
    match = re.search(pattern, file_content, RE_FLAG)
    if match:
        value = match.group(1).strip()
        if is_float:
            try:
                # Limpiamos el valor numérico (quitando cualquier cosa que no sea dígito o punto)
                return float(re.sub(r'[^\d.]', '', value.replace(',', '.')))
            except ValueError:
                return 0.0
        if is_date:
            try:
                return datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m/%Y')
            except ValueError:
                return None
        return value
    # escribir_log(f"    -> [!][XML] No se encontró el tag <{tag_name}> en el XML.")
    return default if default is not None else (0.0 if is_float else None)


def _extract_cost_by_description(file_content: str, item_description: str) -> float:
    """
    Extrae el valor de <TotalCost> asociado a una <ItemDescription> específica.
    Patrón:
        <ItemDescription>Descripción</ItemDescription>
        ...
        <TotalCost>Valor</TotalCost>
    """

    pattern = (
        r"<ItemDescription>\s*" + re.escape(item_description) + r"\s*</ItemDescription>"
        r"[\s\S]*?<TotalCost>([\d.,]+)</TotalCost>" # Acepta coma y punto
    )
    match = re.search(pattern, file_content, re.DOTALL | re.IGNORECASE)
    if match:
        cost_str = match.group(1).strip().replace(',', '.') # Normaliza coma a punto
        try:
            return float(cost_str)
        except ValueError:
            escribir_log(f"    -> [!][XML] No se pudo convertir el coste a float para la descripción '{item_description}': '{cost_str}'")
            return 0.0
    # escribir_log(f"    -> [!][XML] No se encontró el coste para la descripción '{item_description}'")
    return 0.0


# --------------------------------------------------------------------------------
# --- FUNCIÓN PRINCIPAL DE PROCESAMIENTO (REGEX) ---
# --------------------------------------------------------------------------------

def procesar_xml_local_endesa(factura: FacturaEndesa, filepath: str):
    """
    Procesa un archivo XML local para extraer datos y rellenar el objeto FacturaEndesa.
    Parámetros:
        factura (FacturaEndesa): Objeto de factura a rellenar.
        filepath (str): Ruta al archivo XML local.
    Retorna:
        bool: True si el procesamiento fue exitoso, False en caso contrario.
    """
    

    # === 0. Lectura y limpieza del archivo ===
    try:
        with open(filepath, 'r', encoding='latin-1') as f:
            raw_content = f.read()
            content = _clean_text(raw_content) # Eliminamos NS para facilitar el Regex 
    except FileNotFoundError:
        escribir_log(f"    -> [ERROR XML] Archivo no encontrado en: {filepath}")
        return False
    except Exception as e:
        escribir_log(f"     -> [ERROR XML] Error al leer el archivo (código): {e}")
        return False



    # === 1. INICIALIZACIÓN DE VARIABLES ===
    importe_de_potencia = 0.0
    kw_totales = 0.0
    importe_consumo = 0.0
    importe_exceso_potencia = 0.0
    


    # === 2. EXTRACCIÓN DE DATOS BÁSICOS (VALORES SIMPLES) ===
    # Tarifa
    factura.tarifa = _extract_simple_value(content, 'CodigoTarifa', default='N/A')
    # Dirección de Suministro
    dir_calle = _extract_simple_value(content, 'Direccion', default='')
    dir_cp = _extract_simple_value(content, 'CodigoPostal', default='')
    dir_pob = _extract_simple_value(content, 'Poblacion', default='')
    dir_prov = _extract_simple_value(content, 'Provincia', default='')
        # Concatenamos partes de la dirección
    factura.direccion_suministro = f"{dir_calle}, {dir_cp} {dir_pob}, {dir_prov}".strip(", ")
    
    # Mes Facturado 
    transaction_date = _extract_simple_value(content, 'TransactionDate')
        # Asignación del mes facturado basado en la fecha de transacción
    if transaction_date:
        try:
            nombres_meses = {
                1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
                5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
                9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
            }
            
            dt = datetime.strptime(transaction_date, '%Y-%m-%d')
            factura.mes_facturado = nombres_meses.get(dt.month, "DESCONOCIDO")
        except ValueError:
            escribir_log(f"    -> [!][XML] No se pudo parsear la fecha: {transaction_date}")
            pass
    
    # Base Imponible
    base_imponible = _extract_simple_value(content, 'TotalGrossAmountBeforeTaxes', is_float=True)
        # Validación de base imponible
    if base_imponible == 0.0:
        escribir_log(f"    -> [!][XML] Base imponible con importe 0.0")
        return False
    factura.importe_base_imponible = base_imponible

    # Importe Facturado
    factura.importe_facturado = _extract_simple_value(content, 'InvoiceTotal', is_float=True)
    
    # Extracción segura de la fecha de cobro
    factura.fecha_de_factura = _extract_simple_value(content, 'InstallmentDueDate', is_date=True)
    


    # === 3. EXTRACCIÓN DE CONCEPTOS ÚNICOS ===
    # Impuesto Elécytrico
    factura.importe_impuesto_electrico = _extract_cost_by_description(content, 'Impuesto Electricidad')
    # Alquiler Equipo
    factura.importe_alquiler_equipos = _extract_cost_by_description(content, 'Alquiler del contador')
    # Bono Social
    factura.importe_bono_social = _extract_cost_by_description(content, 'Financiación Bono Social') 
    # Reactiva
    factura.importe_reactiva = _extract_cost_by_description(content, 'Complemento por Energía Reactiva')
    # Regularización Eficiencia Energética
    factura.importe_regularización_eficiencia_energetica = _extract_cost_by_description(content, 'Regularización Fondo Nacional Eficiencia Energía')
        
        # Otros Conceptos (€)
    factura.importe_otros_conceptos = round( 
        factura.importe_alquiler_equipos + factura.importe_bono_social + factura.importe_reactiva + factura.importe_regularización_eficiencia_energetica, 2
    )



    # === 4. EXTRACCIÓN DE IMPORTES DETALLADOS ===
    ## Potencia P{1-6} (€)
    for i in range(1, 7):
        attr = f'potencia_p{i}'
        desc = f'Pot. P{i}'
        cost = _extract_cost_by_description(content, desc)
        setattr(factura, attr, cost)
        importe_de_potencia += cost
        
        # Potencia Total (€)
    factura.importe_de_potencia = round(importe_de_potencia, 2)
    
    ## Importe Consumo P{1-6} (€)
    for i in range(1, 7):
        attr = f'importe_consumo_p{i}'
        desc_consumo = f'Consumo P{i}'
        cost_consumo = _extract_cost_by_description(content, desc_consumo)
        setattr(factura, attr, cost_consumo)
        importe_consumo += cost_consumo

    ## Energia Precio Indexado P{1-6} (€)
    for i in range(1, 7):    
        attr = f'energia_precio_indexado_p{i}'
        desc_index = f'Energia precio indexado P{i}'
        cost_index = _extract_cost_by_description(content, desc_index)
        setattr(factura, attr, cost_index)
        importe_consumo += cost_index
        
        # Importe Consumo Total (€) = Sumatorio Importe_Consumo_P{i} + Energia_Precio_Indexado P{i}
    factura.importe_consumo = round(importe_consumo, 2)

    ## Exceso de Potencia P{1-6} (€)
    for i in range(1, 7):
        attr = f'importe_exceso_potencia_p{i}'
        desc = f'Exceso Pot. P{i}'
        cost = _extract_cost_by_description(content, desc)
        setattr(factura, attr, cost)
        importe_exceso_potencia += cost
        
        # Exceso de Potencia Total (€)
    factura.importe_exceso_potencia = round(importe_exceso_potencia, 2)
    
    

    # === 5. EXTRACCIÓN DE CONSUMOS KW ===

    # Consumo KW P{1-6} (kWh)
    for i in range(1, 7):
        attr = f'consumo_kw_p{i}'
        dh_code = f'AEA{i}'
        pattern = (
            r"<CodigoDH>" + re.escape(dh_code) + r"</CodigoDH>"
            r"[\s\S]*?<ConsumoCalculado>([0-9.]+)</ConsumoCalculado>"
        )
        match = re.search(pattern, content, RE_FLAG)
        if match:
            consumo = float(match.group(1).strip())
            setattr(factura, attr, consumo)
            kw_totales += consumo
        else:
            setattr(factura, attr, 0.0)

        # Consumo Total (kWh)
    factura.kw_totales = round(kw_totales, 2)
    
    # === 6. EXTRACCIÓN DE NÚMERO DE DÍAS DE FACTURACIÓN ===
    try:
        # Extraemos la cantidad de días del tag <Quantity> asociado a 'Alquiler del contador'
        quantity_match = re.search(
            r"<ItemDescription>\s*Alquiler del contador\s*</ItemDescription>[\s\S]*?<Quantity>([0-9.]+)</Quantity>",
            content,
            RE_FLAG
        )
        if quantity_match:
            factura.num_dias = int(float(quantity_match.group(1).strip()))
    except Exception:
        escribir_log(f"    -> [!][XML] No se pudo extraer el número de días de facturación.")
        pass

    escribir_log(f"    -> [OK] [XML PARSED] Datos extraídos del XML para factura {factura.numero_factura} ({factura.cup})")
    return True
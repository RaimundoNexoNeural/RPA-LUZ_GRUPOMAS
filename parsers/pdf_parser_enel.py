import os
import json
from datetime import datetime
from openai import OpenAI

from logs import escribir_log
from modelos_datos import FacturaEnel
from config import PROMPT_ENEL_PATH, MODEL


def procesar_pdf_local_enel(factura: FacturaEnel, ruta_pdf: str) -> bool:
    '''
    Procesa una factura de Enel en formato PDF utilizando la API de OpenAI para extraer datos.
    Parametros:
        factura (FacturaEndesaDistribucion): Objeto de la factura donde se almacenarán los datos extraídos.
        ruta_pdf (str): Ruta local al archivo PDF de la factura.
    Retorna:
        bool: True si el procesamiento fue exitoso, False en caso de error.
    '''

    return True
    # === 0. Configuración de la API de OpenAI ===
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        escribir_log("    -> [ERROR] No se encontró la variable de entorno OPENAI_API_KEY")
        factura.error_RPA = True
        factura.msg_error_RPA += "Error: No se encontró la variable de entorno OPENAI_API_KEY"
        return False

    client = OpenAI(api_key=api_key)
    file_id = None


    # === 1. Procesamiento del PDF (OCR + LLM)===
    try:
        # A. Esquema dinámico compatible con Strict Mode (FacturaEndesaDistribucion)
        esquema_pydantic = FacturaEnel.model_json_schema()
        esquema_pydantic["additionalProperties"] = False
        esquema_pydantic["required"] = list(esquema_pydantic["properties"].keys())

        # B. Cargar prompt 
        with open(PROMPT_ENEL_PATH, "r", encoding="utf-8") as f:
            prompt_text = f.read()

        # C. Subir archivo PDF
        with open(ruta_pdf, "rb") as f:
            file_upload = client.files.create(file=f, purpose="assistants")
            file_id = file_upload.id

        # D. Llamada a la API
        response = client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": file_id},
                        {"type": "input_text", "text": prompt_text}
                    ]
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "extraccion_factura_electrica",
                    "strict": True,
                    "schema": esquema_pydantic
                }
            }
        )

        # === 2. Revision, Guardado y Procesado de datos extraídos ===
        datos_extraidos = json.loads(response.output_text)


        for campo, valor_ocr in datos_extraidos.items():


        # A. Decidir si se actualiza el valor del campo en el objeto factura (Omitible) --> Revisar política

            valor_actual = getattr(factura, campo)
            valor_por_defecto = FacturaEnel.model_fields[campo].default

            # Saltamos si el OCR no devolvió nada útil
            if valor_ocr is None or str(valor_ocr).lower() == "null" or valor_ocr == "":
                #escribir_log(f"\t    -->[!][OCR] Valor no extraido para el atributo '{campo}' | Valor OCR: '{valor_ocr}'")
                continue

            # Si el valor actual es el valor por defecto, lo actualizamos con el valor OCR
            if valor_actual == valor_por_defecto:
                setattr(factura, campo, valor_ocr)
                
            # Si el valor actual es diferente del valor por defecto
            else:
                # Comparamos si el valor extraído coincide con el que ya teníamos
                if valor_actual != valor_ocr:
                    # escribir_log(
                    #     f"    -->[!][OCR] Conflicto de valores para el atributo '{campo}' | "
                    #     f"Valor actual: '{valor_actual}' | Valor OCR: '{valor_ocr}'"
                    # )
                    pass
        

        # B. Procesamiento adicional de campos específicos
        
            # B.1 Mes facturado
        if factura.fecha_fin_periodo and factura.fecha_fin_periodo != "N/A":
            try:
                nombres_meses = {
                    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
                    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
                    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
                }
                f_fin_str = factura.fecha_fin_periodo.replace("/", "-")
                dt_fin = datetime.strptime(f_fin_str, '%d-%m-%Y')
                factura.mes_facturado = nombres_meses.get(dt_fin.month, "DESCONOCIDO")
            except Exception as e_fecha:
                escribir_log(f"    -->[!][OCR] No se pudo calcular el mes facturado a partir de la fecha_fin_periodo '{factura.fecha_fin_periodo}': {str(e_fecha)[:100]}")
        

            # B.2 Calculo de num_dias
        if (factura.fecha_inicio_periodo and factura.fecha_inicio_periodo != "N/A") and (factura.fecha_fin_periodo and factura.fecha_fin_periodo != "N/A"):
            try:
                f_ini_str = factura.fecha_inicio_periodo.replace("/", "-")
                dt_ini = datetime.strptime(f_ini_str, '%d-%m-%Y') 
                diferencia = abs((dt_fin - dt_ini).days)
                factura.num_dias = diferencia
                
            except Exception as e_dias:
                escribir_log(f"    -->[!][OCR] No se pudo calcular el número de días: {str(e_dias)[:100]}")
            
            
            # B.3 Cálculo de Importe de Potencia (Peaje + Cargos)
        p_peaje = factura.termino_de_potencia_peaje or 0.0
        p_cargos = factura.termino_de_potencia_cargos or 0.0
        factura.importe_de_potencia = round(p_peaje + p_cargos, 2)

            # B.4 Cálculo de Importe ATR (Energía Peaje + Energía Cargos)
        e_peaje = factura.termino_de_energia_peaje or 0.0
        e_cargos = factura.termino_de_energia_cargos or 0.0
        factura.importe_atr = round(e_peaje + e_cargos, 2)




        escribir_log(f"    -> [OK] [PDF OCR PARSER] Datos extraídos del PDF para factura {factura.numero_factura} ({factura.cup})")
        return True

    except Exception as e:
        escribir_log(f"    -> [ERROR] Error al procesar la factura PDF {factura.numero_factura} ({factura.cup}): {str(e)}")
        factura.error_RPA = True
        factura.msg_error_RPA += f"Error al procesar PDF: {str(e)}"
        return False
    
    # === 3. Limpieza de recursos temporales ===
    finally:
        if file_id:
            client.files.delete(file_id)
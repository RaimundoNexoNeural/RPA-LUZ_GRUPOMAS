import os
import json
from openai import OpenAI
from datetime import datetime

from utils.logs import escribir_log
from logic.logs_logic import log, mail_handler
from utils.modelos_datos import FacturaEndesa
from config import PROMPT_ENDESA_PATH, MODEL

# --------------------------------------------------------------------------------
# --- FUNCIÓN PRINCIPAL DE PROCESAMIENTO (OCR) ---
# --------------------------------------------------------------------------------

def procesar_pdf_local_endesa(factura: FacturaEndesa, ruta_pdf: str) -> bool:
    """
    Procesa una factura de Endesa en formato PDF utilizando la API de OpenAI para extraer datos.
    Parametros:
        factura (FacturaEndesa): Objeto de la factura donde se almacenarán los datos extraídos.
        ruta_pdf (str): Ruta local al archivo PDF de la factura.
    Retorna:
        bool: True si el procesamiento fue exitoso, False en caso de error.
    """


    # === 0. Configuración de la API de OpenAI ===
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        escribir_log("    -> [ERROR] No se encontró la variable de entorno OPENAI_API_KEY")
        log.error("    -> [ERROR] No se encontró la variable de entorno OPENAI_API_KEY")
        factura.error_RPA = True
        factura.msg_error_RPA += "Error: No se encontró la variable de entorno OPENAI_API_KEY"
        return False

    log.debug(f"Iniciando cliente OpenAI para procesar PDF: {os.path.basename(ruta_pdf)}")
    client = OpenAI(api_key=api_key)
    file_id = None

    # === 1. Procesamiento del PDF (OCR + LLM)===
    try:
        # A. Esquema dinámico compatible con Strict Mode (FacturaEndesa)
        esquema_pydantic = FacturaEndesa.model_json_schema()
        esquema_pydantic["additionalProperties"] = False 
        esquema_pydantic["required"] = list(esquema_pydantic["properties"].keys())

        # B. Cargar prompt
        log.debug(f"Cargando prompt desde: {PROMPT_ENDESA_PATH}")
        with open(PROMPT_ENDESA_PATH, "r", encoding="utf-8") as f:
            prompt_text = f.read()

        # C. Subir archivo PDF
        log.debug(f"Subiendo archivo a OpenAI: {ruta_pdf}")
        with open(ruta_pdf, "rb") as f:
            file_upload = client.files.create(file=f, purpose="assistants")
            file_id = file_upload.id
        log.debug(f"Archivo subido con éxito. ID: {file_id}")

        # D. Llamada a la API
        log.debug(f"Enviando petición a modelo {MODEL} con JSON Schema estricto")
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
        log.debug("Datos JSON extraídos correctamente de la respuesta de OpenAI")


        # A. Actualización dinámica de campos en el objeto factura usando setattr
        for campo, valor_ocr in datos_extraidos.items():
            setattr(factura, campo, valor_ocr)
            

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
                log.debug(f"Mes facturado calculado: {factura.mes_facturado}")
            except Exception as e_fecha:
                escribir_log(f"    -->[!][OCR] No se pudo calcular el mes facturado a partir de la fecha_fin_periodo '{factura.fecha_fin_periodo}': {str(e_fecha)[:100]}")
                log.warning(f"    -->[!][OCR] No se pudo calcular el mes facturado: {str(e_fecha)[:100]}")
        
            # B.2 Año facturado
        if factura.fecha_fin_periodo and factura.fecha_fin_periodo != "N/A":
            try:
                f_fin_str = factura.fecha_fin_periodo.replace("/", "-")
                dt_fin = datetime.strptime(f_fin_str, '%d-%m-%Y')
                factura.anno_facturado = str(dt_fin.year)
                log.debug(f"Año facturado calculado: {factura.anno_facturado}")
            except Exception as e_fecha:
                escribir_log(f"    -->[!][OCR] No se pudo calcular el año facturado a partir de la fecha_fin_periodo '{factura.fecha_fin_periodo}': {str(e_fecha)[:100]}")
                log.warning(f"    -->[!][OCR] No se pudo calcular el año facturado: {str(e_fecha)[:100]}")



        escribir_log(f"    -> [OK] [PDF OCR PARSER] Datos extraídos del PDF para factura {factura.numero_factura} ({factura.cup})")
        log.info(f"\t   -> [OK] [PDF OCR PARSER] Datos extraídos del PDF para factura {factura.numero_factura}")
        return True


    except Exception as e:
        escribir_log(f"    -> [ERROR] Error al procesar la factura PDF {factura.numero_factura} ({factura.cup}): {str(e)}")
        log.error(f"    -> [ERROR] Error al procesar la factura PDF {factura.numero_factura}: {str(e)}", exc_info=True)
        factura.error_RPA = True
        factura.msg_error_RPA += f"Error al procesar PDF: {str(e)}"
        return False
    
    # === 3. Limpieza de recursos temporales ===
    finally:
        if file_id:
            log.debug(f"Eliminando archivo temporal de OpenAI con ID: {file_id}")
            client.files.delete(file_id)
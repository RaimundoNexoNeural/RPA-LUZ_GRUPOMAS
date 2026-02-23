import base64
import os
import mailchimp_transactional as MailchimpTransactional
from mailchimp_transactional.api_client import ApiClientError
from utils.logs import escribir_log
from logic.logs_logic import log, mail_handler
from config import MAILCHIMP_API_KEY, SENDER_EMAIL

# === 1. LÓGICA DE NOTIFICACIONES POR CORREO ELECTRÓNICO === 

# MAIL.1 Envío de factura procesada por email
async def enviar_factura_email(destinatarios: list, ruta_pdf: str, numero_factura: str, cup: str):
    '''
    Envía una factura procesada en formato PDF a una lista cerrada de correos utilizando Mailchimp Transactional (Mandrill).
    Parametros:
        - destinatarios (list): Lista de cadenas con las direcciones de correo electrónico de destino.
        - ruta_pdf (str): Ruta local al archivo físico de la factura a adjuntar.
        - numero_factura (str): Identificador numérico de la factura para el asunto y cuerpo.
        - cup (str): Código Universal de Punto de Suministro asociado.
    Retorna
        - bool: True si el envío fue exitoso o quedó en cola; False en caso de error.
    '''
    # A. Validaciones de requisitos previos
    # A.1. Verificación de clave de API
    if not MAILCHIMP_API_KEY:
        escribir_log("[ERROR][MAIL] No se encontró la API Key de Mailchimp Transactional.")
        log.error("[ERROR][MAIL] No se encontró la API Key de Mailchimp Transactional.")
        return False

    # A.2. Verificación de existencia del adjunto
    if not os.path.exists(ruta_pdf):
        escribir_log(f"[ERROR][MAIL] Archivo no encontrado: {ruta_pdf}")
        log.error(f"[ERROR][MAIL] Archivo no encontrado: {ruta_pdf}")
        return False

    try:
        # B. Inicialización del cliente de Mailchimp
        log.debug(f"Inicializando cliente Mailchimp para enviar factura {numero_factura}")
        client = MailchimpTransactional.Client(MAILCHIMP_API_KEY)
        
        # C. Preparación del archivo adjunto
        # C.1. Lectura del archivo en binario y codificación a Base64
        log.debug(f"Codificando archivo PDF para adjunto: {os.path.basename(ruta_pdf)}")
        with open(ruta_pdf, "rb") as f:
            pdf_encoded = base64.b64encode(f.read()).decode('utf-8')

        # D. Configuración de la estructura del mensaje (Payload)
        message = {
            "from_email": SENDER_EMAIL,
            "subject": f"Factura Disponible - Nº {numero_factura} | CUP: {cup}",
            "text": f"Se adjunta la factura procesada con número {numero_factura} correspondiente al suministro {cup}.",
            "to": [{"email": email, "type": "to"} for email in destinatarios],
            "attachments": [
                {
                    "type": "application/pdf",
                    "name": os.path.basename(ruta_pdf),
                    "content": pdf_encoded
                }
            ]
        }

        # E. Ejecución del envío mediante la API
        log.debug(f"Enviando petición de correo a Mailchimp para {len(destinatarios)} destinatarios")
        response = client.messages.send({"message": message})
        
        # F. Evaluación del resultado de la operación
        # F.1. Comprobación de estados válidos (Enviado o En cola)
        if response[0]['status'] in ['sent', 'queued']:
            escribir_log(f"    [OK] Correo enviado correctamente (Status: {response[0]['status']})")
            log.info(f"\t   -> [OK] Correo enviado correctamente (Status: {response[0]['status']})")
            return True
        
        # F.2. Gestión de rechazos por parte del proveedor de mail
        else:
            escribir_log(f"    [ADVERTENCIA] El correo no se envió. Razón: {response[0].get('reject_reason')}")
            log.warning(f"\t   --> [ADVERTENCIA] El correo no se envió. Razón: {response[0].get('reject_reason')}")
            return False

    # G. Control de errores específicos y genéricos
    # G.1. Errores de comunicación con la API de Mailchimp
    except ApiClientError as error:
        escribir_log(f"    [ERROR][MAIL] Fallo en la API de Mailchimp: {error.text}")
        log.error(f"\t   --> [ERROR][MAIL] Fallo en la API de Mailchimp: {error.text}")
        return False
    
    # G.2. Errores inesperados de ejecución
    except Exception as e:
        escribir_log(f"    [ERROR][MAIL] Error inesperado en envío: {str(e)}")
        log.error(f"\t   --> [ERROR][MAIL] Error inesperado en envío: {str(e)}", exc_info=True)
        return False
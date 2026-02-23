import base64
import os
import mailchimp_transactional as MailchimpTransactional
from mailchimp_transactional.api_client import ApiClientError
from logs import escribir_log
from config import MAILCHIMP_API_KEY, SENDER_EMAIL



async def enviar_factura_email(destinatarios: list, ruta_pdf: str, numero_factura: str, cup: str):
    """
    Envía una factura procesada a una lista cerrada de correos.
    """
    if not MAILCHIMP_API_KEY:
        escribir_log("[ERROR][MAIL] No se encontró la API Key de Mailchimp Transactional.")
        return False

    if not os.path.exists(ruta_pdf):
        escribir_log(f"[ERROR][MAIL] Archivo no encontrado: {ruta_pdf}")
        return False

    try:
        client = MailchimpTransactional.Client(MAILCHIMP_API_KEY)
        
        # 1. Leer y codificar el archivo PDF
        with open(ruta_pdf, "rb") as f:
            pdf_encoded = base64.b64encode(f.read()).decode('utf-8')

        # 2. Configurar el mensaje
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

        # 3. Enviar
        response = client.messages.send({"message": message})
        
        if response[0]['status'] in ['sent', 'queued']:
            escribir_log(f"    [OK] Correo enviado correctamente (Status: {response[0]['status']})")
            return True
        else:
            escribir_log(f"    [ADVERTENCIA] El correo no se envió. Razón: {response[0].get('reject_reason')}")
            return False

    except ApiClientError as error:
        escribir_log(f"    [ERROR][MAIL] Fallo en la API de Mailchimp: {error.text}")
        return False
    except Exception as e:
        escribir_log(f"    [ERROR][MAIL] Error inesperado en envío: {str(e)}")
        return False
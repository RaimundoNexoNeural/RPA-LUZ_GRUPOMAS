import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from logging.handlers import TimedRotatingFileHandler
# Las constantes se cargan desde config.py
from config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_RECEIVER, ENTORNO

# === 0. CONFIGURACIÓN GLOBAL DE LOGGING ===
NIVEL_GLOBAL = logging.DEBUG

# === 1. GESTIÓN DE ALERTAS POR CORREO ELECTRÓNICO ===

class GroupedMailHandler(logging.Handler):
    '''
    Handler personalizado de logging que acumula mensajes de alta severidad para su envío masivo.
    Diseñado para evitar el spam de correos enviando todos los fallos detectados en un único mensaje al finalizar el proceso.
    '''
    # LOG.1 Inicialización del manejador de correo
    def __init__(self):
        '''
        Inicializa el buffer de mensajes acumulados.
        '''
        super().__init__()
        self.buffer = []

    # LOG.2 Captura de registros de error
    def emit(self, record):
        '''
        Filtra y almacena registros que tengan un nivel igual o superior a ERROR.
        Parametros:
            - record (LogRecord): Registro de log generado por la aplicación.
        '''
        # A. Verificación del nivel de severidad del registro
        if record.levelno >= logging.ERROR:
            # B. Formateo y almacenamiento en el buffer temporal
            self.buffer.append(self.format(record))

    # LOG.3 Envío consolidado de alertas
    def flush_to_email(self):
        '''
        Envía todos los mensajes acumulados en el buffer a través de SMTP si el entorno es PRODUCCION.
        Parametros:
        Retorna:
        '''
        # A. Verificación de condiciones de envío y simulación en desarrollo
        if not self.buffer or ENTORNO != "PRODUCCION":
            if self.buffer and ENTORNO != "PRODUCCION":
                print(f"[SIMULACIÓN EMAIL] Se habrían enviado {len(self.buffer)} errores.")
            self.buffer = []
            return

        # B. Construcción del mensaje de correo electrónico (MIME)
        try:
            msg = MIMEMultipart()
            msg['From'] = SMTP_USER
            msg['To'] = EMAIL_RECEIVER
            msg['Subject'] = "ALERTA RPA: Errores detectados en ejecución"
            
            # B.1. Consolidación de todos los mensajes de error del buffer en el cuerpo del correo
            body = "Errores detectados:\n\n" + "\n".join(self.buffer)
            msg.attach(MIMEText(body, 'plain'))

            # C. Conexión y transmisión vía servidor SMTP
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls() # C.1. Cifrado de la conexión
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        except Exception as e:
            print(f"Error enviando correo de logs: {e}")
        finally:
            # D. Limpieza del buffer tras intento de envío
            self.buffer = []


# === 2. CONFIGURACIÓN DEL SISTEMA DE TRAZABILIDAD ===

# LOG.4 Configuración y despliegue del Logger
def configurar_logs():
    '''
    Inicializa el sistema de logs creando los directorios necesarios y configurando handlers rotativos por nivel.
    La estructura resultante es:
        logs/
        ├── DEBUG.txt                (activo)
        ├── DEBUG.YYYY-MM-DD.txt     (histórico)  <-- rotación controlada por TimedRotatingFileHandler
        ├── INFO.txt
        ├── INFO.YYYY-MM-DD.txt
        ...
    Cada categoría mantiene hasta 15 archivos históricos y los registros de todos los niveles
    siempre se escriben además en DEBUG.
    Parametros:
    Retorna
        - tuple: (logger instance, mail_handler instance) para su uso en el robot.
    '''
    # A. Preparación del sistema de archivos para almacenamiento de logs
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # B. Definición del formato estandarizado: [Día/Mes/Año Hora:Minuto:Segundo] Mensaje
    formato = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%d/%m/%Y %H:%M:%S')

    # C. Inicialización del Logger principal con el nivel global definido
    logger = logging.getLogger("RPA_Endesa")
    logger.setLevel(NIVEL_GLOBAL)

    # D. Limpieza de handlers previos para evitar duplicidad de registros en recargas
    if logger.hasHandlers():
        logger.handlers.clear()

    # E. Definición de la estructura de archivos por nivel de severidad
    niveles = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    # F. Creación iterativa de manejadores de archivos rotativos
    for nombre, nivel in niveles.items():
        filename = os.path.join(log_dir, f"{nombre}.txt")
        
        # F.1. Configuración de rotación diaria con historial de 15 días
        handler = TimedRotatingFileHandler(
            filename, when='D', interval=1, backupCount=15, encoding='utf-8'
        )
        handler.suffix = "%Y-%m-%d.txt" 
        handler.setLevel(nivel)
        handler.setFormatter(formato)

        # G. Aplicación de lógica de filtrado estricto
        # G.1. El archivo DEBUG actúa como log maestro (contiene todo)
        # G.2. El resto de archivos contienen únicamente su nivel específico mediante StrictLevelFilter
        if nombre != "DEBUG":
            class StrictLevelFilter(logging.Filter):
                def __init__(self, lvl): self.lvl = lvl
                def filter(self, record): return record.levelno == self.lvl
            handler.addFilter(StrictLevelFilter(nivel))
        
        logger.addHandler(handler)

    # H. Integración del manejador de alertas por correo
    mail_handler = GroupedMailHandler()
    mail_handler.setFormatter(formato)
    logger.addHandler(mail_handler)

    return logger, mail_handler

# === 3. INICIALIZACIÓN AUTOMÁTICA ===
log, mail_handler = configurar_logs()
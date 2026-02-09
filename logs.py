from datetime import datetime

def escribir_log(mensaje, mostrar_en_consola=True, mostrar_tiempo=True, pretexto="\t\t"):
        '''
        Registra un mensaje en el archivo de log y opcionalmente lo muestra en la consola.
        '''
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        if mostrar_tiempo:
            linea = f"{pretexto}{timestamp} {mensaje}\n"
        else:
            linea = f"{pretexto} {mensaje}\n"
        with open("logs/log.txt", "a", encoding="utf-8") as log_file:
            log_file.write(linea)
        if mostrar_en_consola:
            print(linea, end="")
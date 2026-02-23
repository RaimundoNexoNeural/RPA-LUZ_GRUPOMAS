### IMPORTACIÓN DE DEPENDENCIAS
import asyncio

    # Navegador Asíncrono
from utils.navegador import NavegadorAsync
    # Clases Facturas
from utils.modelos_datos import FacturaEndesa, FacturaEnel
    # Logs
from utils.logs import escribir_log
from logic.logs_logic import log, mail_handler
    # utilidades CSV/registro
from parsers.exportar_datos import cargar_registro_procesados
    # Logics
from logic.endesa_logic import _iniciar_sesion_endesa, _aceptar_cookies_endesa, _realizar_busqueda_facturas_endesa, _extraer_tabla_facturas_endesa
from logic.enel_logic import _iniciar_sesion_enel, _obtener_todos_los_roles, _seleccionar_rol_especifico, _aplicar_filtros_fechas, _extraer_tabla_facturas_enel
    # CONSTANTES DE CONFIGURACION
from config import MAX_LOGIN_ATTEMPTS,URL_LOGIN_ENDESA,USER_ENDESA,PASSWORD_ENDESA, MAX_LOGIN_ATTEMPTS, URL_LOGIN_ENEL, USER_ENEL, PASSWORD_ENEL


# === 1. LÓGICA PRINCIPAL DEL ROBOT ENDESA (CLIENTES) === 

# END.1 Ejecución del flujo de extracción para portal Endesa
async def ejecutar_robot_endesa( fecha_desde: str, fecha_hasta:str, lista_cups: list = None) -> list[FacturaEndesa]:
    '''
    Coordina el proceso completo de login, búsqueda y extracción de facturas en el portal de Endesa Clientes.
    Parametros:
        - fecha_desde (str): Límite inicial del rango de búsqueda.
        - fecha_hasta (str): Límite final del rango de búsqueda.
        - lista_cups (list): Opcionalmente, una lista de CUPS específicos para filtrar.
    Retorna
        - list[FacturaEndesa]: Lista de objetos factura con los datos extraídos y procesados.
    '''
    robot = NavegadorAsync()
    facturas_totales = []
    login_successful = False
    total_cups_log = len(lista_cups) if lista_cups else "TODOS LOS"

    try:
        # A. Preparación de registros y configuración previa
        # A.1. Precargar fichero de procesados para optimizar verificaciones de duplicados
        cargar_registro_procesados('endesa')
        from config import REPROCESADO
        if REPROCESADO:
            escribir_log("[CONFIG] REPROCESADO=True -> se ignorarán marcas anteriores.")
            log.info("[CONFIG] REPROCESADO=True -> se ignorarán marcas anteriores.")

        # B. Inicio del proceso y gestión de autenticación (Login)
        escribir_log(f"    [INICIO] Iniciando proceso RPA-ENDESA para {total_cups_log} CUPS. \n\n{'='*40} ",pretexto="\n",mostrar_tiempo=False)
        log.info(f"\n    [INICIO] Iniciando proceso RPA-ENDESA para {total_cups_log} CUPS. \n\n{'='*40}")
        
        for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
            escribir_log(f"[LOGIN] Intento {attempt}/{MAX_LOGIN_ATTEMPTS}...",pretexto="\n\t")
            log.info(f"\t[LOGIN] Intento {attempt}/{MAX_LOGIN_ATTEMPTS}...")
            
            # B.1. Lanzamiento del navegador y navegación a la URL de acceso
            log.debug("Iniciando instancia de navegador...")
            await robot.iniciar()
            log.debug(f"Navegando a URL de Login: {URL_LOGIN_ENDESA}")
            await robot.goto_url(URL_LOGIN_ENDESA)
            
            # B.2. Intento de validación de credenciales en el portal de Salesforce
            login_successful = await _iniciar_sesion_endesa(robot.get_page(), USER_ENDESA, PASSWORD_ENDESA)
            
            # B.3. Control de flujo según éxito de sesión
            if login_successful:
                escribir_log(f"[LOGIN] Sesión establecida correctamente.")
                log.info("\t\t[LOGIN] Sesión establecida correctamente.")
                break
            
            # B.4. Cierre de contexto en caso de fallo para reintentar limpiamente
            escribir_log(f"[ADVERTENCIA] Intento de login {attempt} fallido. Cerrando contexto.")
            log.warning(f"\t\t[ADVERTENCIA] Intento de login {attempt} fallido.")
            await robot.cerrar()
            
            # B.5. Espera entre reintentos o lanzamiento de excepción crítica tras agotar intentos
            if attempt < MAX_LOGIN_ATTEMPTS:
                await asyncio.sleep(5)
            else:
                log.critical(f"No se pudo acceder al portal tras {MAX_LOGIN_ATTEMPTS} intentos.")
                raise Exception(f"Fallo crítico: No se pudo acceder al portal tras {MAX_LOGIN_ATTEMPTS} intentos.")

        # C. Gestión de elementos post-login
        page = robot.get_page()
        escribir_log(f"[COOCKIES]")
        log.info("\t[COOCKIES]")
        await _aceptar_cookies_endesa(page)
        
        # D. Selección de modo operativo (Por lista o Global)

        # D.1 MODO A: Procesamiento por lista de CUPS proporcionada
        if lista_cups and len(lista_cups) > 0:
            escribir_log(f"    [MODO] Procesando lista de {len(lista_cups)} CUPS.")
            log.info(f"    [MODO] Procesando lista de {len(lista_cups)} CUPS.")

            # D.1.1 Iteración sobre la lista de suministros
            for index, cup_actual in enumerate(lista_cups, start=1):
                escribir_log(f"{'='*80}\nPROCESANDO [{index}/{len(lista_cups)}]: CUP {cup_actual}\n{'='*80}",pretexto="\n",mostrar_tiempo=False)
                log.info(f"\n{'='*80}\nPROCESANDO [{index}/{len(lista_cups)}]: CUP {cup_actual}\n{'='*80}")
                
                try:
                    # D.1.1.1. Ejecución de búsqueda filtrada por CUP y rango temporal
                    escribir_log(f"[BUSQUEDA]")
                    log.info("\t[BUSQUEDA]")
                    await _realizar_busqueda_facturas_endesa(page, fecha_desde, fecha_hasta, cup_actual)
                    
                    # D.1.1.2. Extracción recursiva de todas las páginas de la tabla de resultados
                    escribir_log(f"[EXTRACCIÓN]")
                    log.info("\t[EXTRACCIÓN]")
                    facturas_cup = await _extraer_tabla_facturas_endesa(page)
                    
                    # D.1.1.3. Consolidación de resultados y registro de éxito
                    if facturas_cup:
                        facturas_totales.extend(facturas_cup)
                        escribir_log(f"{'='*80}", mostrar_tiempo=False)
                        escribir_log(f"[OK] {len(facturas_cup)} facturas procesadas con éxito para {cup_actual}.\n{'='*80}")
                        log.info(f"\n{'='*80}\n\t[OK] {len(facturas_cup)} facturas procesadas para {cup_actual}.\n{'='*80}")
                    else:
                        escribir_log(f"{'='*80}", mostrar_tiempo=False)
                        escribir_log(f"[INFO] No se encontraron nuevas facturas registradas para {cup_actual} en este rango.\n{'='*80}")
                        log.info(f"\n{'='*80}\n\t[INFO] No se encontraron facturas para {cup_actual}.\n{'='*80}")
                        
                except Exception as e:
                    # D.1.1.4. Control de errores por CUP: registro del fallo y salto al siguiente elemento
                    error_detalle = str(e)
                    escribir_log(f"{'='*80}", mostrar_tiempo=False)
                    escribir_log(f"[ERROR] Fallo al procesar CUPS {cup_actual}. Detalles del error: \n\t\t{error_detalle}\n{'='*80}")
                    log.error(f"\n{'='*80}\n\t[ERROR] Fallo en CUP {cup_actual}: {error_detalle}\n{'='*80}")
                    
                    registro_error = FacturaEndesa(cup=cup_actual, error_RPA=True, msg_error_RPA=f"ERROR: {error_detalle[:1000]}")
                    facturas_totales.append(registro_error)
                    escribir_log(f"Continuando con el siguiente código de la lista...")
                    log.info("Continuando con el siguiente CUP...")
                    continue
        
        # D.2 MODO B: Búsqueda Global (Sin lista de CUPS)
        else:
            escribir_log(f"{'='*80}", pretexto="\n", mostrar_tiempo=False)
            escribir_log(f"PROCESANDO BÚSQUEDA GLOBAL: Todos los CUPS disponibles\n{'='*80}")
            log.info(f"\n{'='*80}\nPROCESANDO BÚSQUEDA GLOBAL: Todos los CUPS disponibles\n{'='*80}")
            
            try:
                # D.2.1. Aplicación de filtros temporales sin restricción de identificador
                escribir_log(f"[BUSQUEDA]")
                log.info("\t[BUSQUEDA]")
                await _realizar_busqueda_facturas_endesa(page, fecha_desde, fecha_hasta, None)
                
                # D.2.2. Procesamiento masivo de la tabla de resultados
                escribir_log(f"[EXTRACCIÓN]")
                log.info("\t[EXTRACCIÓN]")
                facturas_globales = await _extraer_tabla_facturas_endesa(page)
                
                # D.2.3. Evaluación de resultados globales
                if facturas_globales:
                    facturas_totales.extend(facturas_globales)
                    escribir_log(f"{'='*80}", mostrar_tiempo=False)
                    escribir_log(f"[OK] Búsqueda global finalizada: {len(facturas_globales)} facturas extraídas.\n{'='*80}")
                    log.info(f"\n{'='*80}\n\t[OK] Búsqueda global finalizada: {len(facturas_globales)} facturas.\n{'='*80}")
                else:
                    escribir_log(f"{'='*80}", mostrar_tiempo=False)
                    escribir_log(f"[INFO] No se encontraron nuevas facturas en el rango {fecha_desde} - {fecha_hasta}.\n{'='*80}")
                    log.info(f"\n{'='*80}\n\t[INFO] Sin resultados en búsqueda global.\n{'='*80}")

            except Exception as e:
                # D.2.4. Gestión de errores en modo global
                registro_vacio = FacturaEndesa(cup="GLOBAL", error_RPA=False, msg_error_RPA=f"Error en búsqueda global: {str(e)[:1000]}")
                facturas_totales.append(registro_vacio)
                escribir_log(f"[ERROR] Fallo crítico en la búsqueda global: {str(e)}")
                log.error(f"Fallo crítico en búsqueda global: {str(e)}", exc_info=True)

        # E. Finalización y retorno de datos consolidados
        escribir_log(f"{'='*80}", pretexto="\n\n", mostrar_tiempo=False)
        escribir_log(f"[OK][FIN] Proceso RPA completado.\n\t\tTotal facturas extraídas: {len(facturas_totales)}\n{'='*80}")
        log.info(f"\n\n{'='*80}\n[OK][FIN] Proceso RPA completado.\n\tTotal facturas extraídas: {len(facturas_totales)}\n{'='*80}")
        return facturas_totales

    except Exception as e:
        # F. Captura de fallos críticos a nivel de script
        escribir_log(f"[ERROR] FALLO CRÍTICO EN EL ROBOT: {e}")
        log.critical(f"FALLO CRÍTICO EN EL ROBOT: {e}", exc_info=True)
        raise e

    finally:
        # G. Liberación garantizada de recursos del navegador y envío de correo de logs
        if hasattr(robot, 'browser') and robot.browser:
            await robot.cerrar()
            escribir_log("[SISTEMA] Navegador cerrado y recursos liberados.\n\n")
            log.info("[SISTEMA] Navegador cerrado y recursos liberados.\n")
        
        # Envío consolidado de alertas de error
        mail_handler.flush_to_email()


# === 2. LÓGICA PRINCIPAL DEL ROBOT ENEL (DISTRIBUCIÓN) === 

# ENEL.1 Ejecución del flujo de extracción para portal Enel
async def ejecutar_robot_enel(fecha_desde: str, fecha_hasta: str) -> list[FacturaEnel]:
    '''
    Coordina el proceso de login multi-rol y extracción de facturas del portal e-distribución (Enel).
    Parametros:
        - fecha_desde (str): Límite inicial temporal.
        - fecha_hasta (str): Límite final temporal.
    Retorna
        - list[FacturaEnel]: Lista de facturas de distribución procesadas.
    '''
    robot = NavegadorAsync()
    facturas_totales = []
    login_successful = False
    
    try:
        # A. Configuración y carga de registros
        cargar_registro_procesados('enel')
        from config import REPROCESADO
        if REPROCESADO:
            escribir_log("[CONFIG] REPROCESADO=True -> se ignorarán marcas anteriores.")
            log.info("[CONFIG] REPROCESADO=True -> se ignorarán marcas anteriores.")

        # B. Autenticación en el portal de distribución
        escribir_log(f"    [INICIO] Iniciando proceso RPA-ENEL. \n\n{'='*40} ",pretexto="\n",mostrar_tiempo=False)
        log.info(f"\n    [INICIO] Iniciando proceso RPA-ENEL. \n\n{'='*40}")
        
        for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
            escribir_log(f"[LOGIN] Intento {attempt}/{MAX_LOGIN_ATTEMPTS}...",pretexto="\n\t")
            log.info(f"\t[LOGIN] Intento {attempt}/{MAX_LOGIN_ATTEMPTS}...")

            # B.1. Inicialización y navegación al login de Enel
            log.debug("Iniciando navegador...")
            await robot.iniciar()
            log.debug(f"Navegando a Login Enel: {URL_LOGIN_ENEL}")
            await robot.goto_url(URL_LOGIN_ENEL)
            
            # B.2. Validación de acceso con credenciales de distribución
            login_successful = await _iniciar_sesion_enel(robot.get_page(), USER_ENEL, PASSWORD_ENEL)

            if login_successful:
                escribir_log(f"[LOGIN] Sesión establecida correctamente.")
                log.info("\t\t[LOGIN] Sesión establecida correctamente.")
                break
            
            escribir_log(f"[ADVERTENCIA] Intento de login {attempt} fallido. Cerrando contexto.")
            log.warning(f"\t\t[ADVERTENCIA] Intento de login {attempt} fallido.")
            await robot.cerrar()

            if attempt < MAX_LOGIN_ATTEMPTS:
                await asyncio.sleep(5)
            else:
                log.critical(f"No se pudo acceder al portal Enel tras {MAX_LOGIN_ATTEMPTS} intentos.")
                raise Exception(f"Fallo crítico: No se pudo acceder al portal tras {MAX_LOGIN_ATTEMPTS} intentos.")

        # C. Identificación de perfiles (Roles)
        page = robot.get_page()
        escribir_log(f"[ROLES]")
        log.info("\t[ROLES]")
        roles = await _obtener_todos_los_roles(page)

        # C.1. Verificación de disponibilidad de perfiles de empresa
        if not roles:
            escribir_log(f"    -> [ERROR] No se pudieron obtener los roles disponibles para el usuario.")
            log.error("No se pudieron obtener los roles disponibles.")
            raise Exception("No se pudieron obtener los roles disponibles para el usuario.")
        
        # D. Procesamiento iterativo por cada Rol de empresa
        escribir_log(f"{'='*80}", pretexto="\n", mostrar_tiempo=False)
        escribir_log(f"PROCESANDO BUSQUEDA GLOBAL: Todos los roles disponibles\n{'='*80}")
        log.info(f"\n{'='*80}\nPROCESANDO BUSQUEDA GLOBAL: Todos los roles disponibles\n{'='*80}")
        
        for irol, rol in enumerate(roles):
            escribir_log(f"\n\n[ROL {irol+1} / {len(roles)}]  ({rol.upper()})\n\t\t{'='*40}",mostrar_tiempo=False)
            log.info(f"\n\n[ROL {irol+1} / {len(roles)}]  ({rol.upper()})\n\t\t{'='*40}")
            
            try:
                # D.1. Cambio de contexto de representación de empresa
                log.debug(f"Cambiando al rol: {rol}")
                await _seleccionar_rol_especifico(page, rol)
                
                # D.2. Aplicación de filtros de fecha y validación de respuesta
                escribir_log(f"[BUSQUEDA]")
                log.info("\t[BUSQUEDA]")
                exito_busqueda = await _aplicar_filtros_fechas(page, fecha_desde, fecha_hasta)
                if not exito_busqueda:
                    log.info(f"\t[SKIP] Sin resultados para el rol {rol}")
                    continue

                # D.3. Extracción de metadata de la tabla de distribución
                escribir_log(f"[EXTRACCIÓN]")
                log.info("\t[EXTRACCIÓN]")
                facturas_rol = await _extraer_tabla_facturas_enel(page, len(facturas_totales))
                
                # D.4. Consolidación de resultados del rol actual
                if facturas_rol and len(facturas_rol) > 0:
                    facturas_totales.extend(facturas_rol)
                    escribir_log(f"\n{'='*40}", mostrar_tiempo=False)
                    escribir_log(f"\t[OK] Búsqueda para rol {rol}: {len(facturas_rol)} facturas extraídas.\n{'='*40}", mostrar_tiempo=False)
                    log.info(f"\n{'='*40}\n\t[OK] Búsqueda para rol {rol}: {len(facturas_rol)} facturas.\n{'='*40}")
                else:
                    escribir_log(f"    [INFO] No hay facturas para el rol '{rol}' en el rango {fecha_desde} - {fecha_hasta}.\n\t\t{'='*40}")
                    log.info(f"\t[INFO] No hay facturas para el rol '{rol}'.")
                    continue

            except Exception as e:
                # D.5. Gestión de errores por Rol: registro y continuidad
                error_detalle = str(e)
                registro_error = FacturaEnel(cup="N/A", error_RPA=True, msg_error_RPA=f"ERROR en rol {rol}: {error_detalle[:1000]}")
                facturas_totales.append(registro_error)
                escribir_log(f"[ERROR] Fallo al procesar el rol {rol}. Detalles del error: \n\t\t{error_detalle}\n\t\t{'='*40}")
                log.error(f"\t[ERROR] Fallo al procesar rol {rol}: {error_detalle}")
                continue
        
        # E. Cierre de ejecución y reporte final
        escribir_log(f"{'='*80}", pretexto="\n\n", mostrar_tiempo=False)
        escribir_log(f"[OK][FIN] Proceso RPA completado.\n\t\tTotal facturas extraídas: {len(facturas_totales)}\n{'='*80}")
        log.info(f"\n\n{'='*80}\n[OK][FIN] Proceso RPA completado.\n\tTotal facturas extraídas: {len(facturas_totales)}\n{'='*80}")
        return facturas_totales

    except Exception as e:
        escribir_log(f"[ERROR] FALLO CRÍTICO EN EL ROBOT: {e}")
        log.critical(f"FALLO CRÍTICO EN EL ROBOT ENEL: {e}", exc_info=True)
        raise e
    
    finally:
        await robot.cerrar()
        escribir_log("[SISTEMA] Navegador cerrado.\n")
        log.info("[SISTEMA] Navegador cerrado.\n")
        # Envío consolidado de alertas de error
        mail_handler.flush_to_email()


# === 3. PUNTO DE ENTRADA PARA PRUEBAS (DEBUGGING) === 

if __name__ == "__main__":
    # A. Configuración de parámetros de prueba local
    cups_prueba = ["ES0034111300275021NX0F", "ES0031102570563001SM0F"]
    
    # B. Lanzamiento asíncrono del robot Endesa
    asyncio.run(ejecutar_robot_endesa(
        fecha_desde="01/10/2025", 
        fecha_hasta="31/10/2025", 
        lista_cups=cups_prueba
    ))
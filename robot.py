### IMPORTACIÓN DE DEPENDENCIAS
import asyncio
import re
import csv 
import base64 
import os 
from playwright.async_api import Page, TimeoutError, Locator
    # Navegador Asíncrono
from navegador import NavegadorAsync
    # Clases Facturas
from modelos_datos import FacturaEndesa, FacturaEnel
    # Logs
from logs import escribir_log
    # Logics
from logic.endesa_logic import _iniciar_sesion_endesa, _aceptar_cookies_endesa, _realizar_busqueda_facturas_endesa, _extraer_tabla_facturas_endesa
from logic.enel_logic import _iniciar_sesion_enel, _obtener_todos_los_roles, _seleccionar_rol_especifico, _aplicar_filtros_fechas, _extraer_tabla_facturas_enel
    # CONSTANTES DE CONFIGURACION
from config import MAX_LOGIN_ATTEMPTS,URL_LOGIN_ENDESA,USER_ENDESA,PASSWORD_ENDESA, MAX_LOGIN_ATTEMPTS, URL_LOGIN_ENEL, USER_ENEL, PASSWORD_ENEL




# === ROBOT ENDESA ===
async def ejecutar_robot_endesa( fecha_desde: str, fecha_hasta:str, lista_cups: list = None) -> list[FacturaEndesa]:
    robot = NavegadorAsync()
    facturas_totales = []
    login_successful = False
    total_cups_log = len(lista_cups) if lista_cups else "TODOS LOS"

    try:
        # A. Inicio del proceso y Login

        escribir_log(f"    [INICIO] Iniciando proceso RPA-ENDESA para {total_cups_log} CUPS. \n\n{'='*40} ",pretexto="\n",mostrar_tiempo=False)
        
        for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
            escribir_log(f"[LOGIN] Intento {attempt}/{MAX_LOGIN_ATTEMPTS}...",pretexto="\n\t")
            
            # A.1. Iniciar el navegador y acceder a la URL de login
            await robot.iniciar()
            await robot.goto_url(URL_LOGIN_ENDESA)
            
            # A.2. Intentar iniciar sesión con las credenciales proporcionadas
            login_successful = await _iniciar_sesion_endesa(robot.get_page(), USER_ENDESA, PASSWORD_ENDESA)
            
            # A.3. Verificar si el login fue exitoso y en caso afirmativo, salir del bucle de intentos
            if login_successful:
                escribir_log(f"[LOGIN] Sesión establecida correctamente.")
                break
            
            # A.4. Si el login falla, cerrar el navegador y esperar antes de intentar de nuevo
            escribir_log(f"[ADVERTENCIA] Intento de login {attempt} fallido. Cerrando contexto.")
            await robot.cerrar()
            
            # A.5. Si no se ha logrado el login tras todos los intentos, lanzar una excepción crítica
            if attempt < MAX_LOGIN_ATTEMPTS:
                await asyncio.sleep(5)
            else:
                raise Exception(f"Fallo crítico: No se pudo acceder al portal tras {MAX_LOGIN_ATTEMPTS} intentos.")


        # B. Una vez logueados, aceptamos las cookies y preparamos el entorno para la búsqueda de facturas
        page = robot.get_page()
        escribir_log(f"[COOCKIES]")
        await _aceptar_cookies_endesa(page)
        

        # C. PROCESAMIENTO DE FACTURAS POR CUPS (MODO A) O BÚSQUEDA GLOBAL (MODO B)

        # C.A LISTA DE CUPS PROPORCIONADA (MODO A)
        if lista_cups and len(lista_cups) > 0:
            escribir_log(f"    [MODO] Procesando lista de {len(lista_cups)} CUPS.")

            # C.A.1 Iteramos sobre cada CUP de la lista, realizando el proceso completo de búsqueda y extracción para cada uno
            for index, cup_actual in enumerate(lista_cups, start=1):

                escribir_log(f"{'='*80}", pretexto="\n", mostrar_tiempo=False)
                escribir_log(f"PROCESANDO [{index}/{len(lista_cups)}]: CUP {cup_actual}\n{'='*80}")
                
                try:
                    # C.A.1.1. Rellenar el filtro de búsqueda con el CUP actual y las fechas, y ejecutar la búsqueda
                    escribir_log(f"[BUSQUEDA]")
                    await _realizar_busqueda_facturas_endesa(page, fecha_desde, fecha_hasta, cup_actual)
                    
                    # C.A.1.2. Extraer los datos de la tabla de resultados para el CUP actual, y añadirlos a la lista total de facturas
                    escribir_log(f"[EXTRACCIÓN]")
                    facturas_cup = await _extraer_tabla_facturas_endesa(page)
                    
                    # C.A.1.3. Si se han extraído facturas para el CUP actual, se añaden a la lista total y se registra el éxito en el log.
                    if facturas_cup:
                        facturas_totales.extend(facturas_cup)
                        escribir_log(f"{'='*80}", mostrar_tiempo=False)
                        escribir_log(f"[OK] {len(facturas_cup)} facturas procesadas con éxito para {cup_actual}.\n{'='*80}")
                    
                    # C.A.1.4. Si no se han encontrado facturas para el CUP actual, se registra esta situación en el log y se añade un registro vacío a la lista total de facturas para mantener la trazabilidad.
                    else:
                        escribir_log(f"{'='*80}", mostrar_tiempo=False)
                        escribir_log(f"[INFO] No se encontraron facturas registradas para {cup_actual} en este rango.\n{'='*80}")
                        registro_vacio = FacturaEndesa(cup=cup_actual, 
                                                       error_RPA=False,  
                                                       msg_error_RPA=f"Sin facturas emitidas en el periodo ({fecha_desde} - {fecha_hasta})")
                        facturas_totales.append(registro_vacio)

                # C.A.2. Si ocurre cualquier error durante el proceso de búsqueda o extracción para el CUP actual, se captura la excepción, se registra el error en el log con detalles del mismo, se añade un registro de error a la lista total de facturas para ese CUP, y se continúa con el siguiente CUP de la lista sin detener el proceso completo.
                except Exception as e:
                    error_detalle = str(e)
                    escribir_log(f"{'='*80}", mostrar_tiempo=False)
                    escribir_log(f"[ERROR] Fallo al procesar CUPS {cup_actual}. Detalles del error: \n\t\t{error_detalle}\n{'='*80}")
                    
                    registro_error = FacturaEndesa(cup=cup_actual, 
                                                   error_RPA=True, 
                                                   msg_error_RPA=f"ERROR: {error_detalle[:1000]}")
                    facturas_totales.append(registro_error)

                    escribir_log(f"Continuando con el siguiente código de la lista...")
                    continue
        
        # C.B MODO GLOBAL (SIN LISTA DE CUPS) - Se realiza una búsqueda general sin rellenar el filtro de CUP.
        else:
            
            escribir_log(f"{'='*80}", pretexto="\n", mostrar_tiempo=False)
            escribir_log(f"PROCESANDO BÚSQUEDA GLOBAL: Todos los CUPS disponibles\n{'='*80}")
            

            try:
                # C.B.1. Rellenar los filtros de fecha sin especificar ningún CUP, y ejecutar la búsqueda para obtener todas las facturas disponibles en ese rango de fechas.
                escribir_log(f"[BUSQUEDA]")
                await _realizar_busqueda_facturas_endesa(page, fecha_desde, fecha_hasta, None)
                
                # C.B.2. Extraer los datos de la tabla de resultados para la búsqueda global, y añadirlos a la lista total de facturas.
                escribir_log(f"[EXTRACCIÓN]")
                facturas_globales = await _extraer_tabla_facturas_endesa(page)
                
                # C.B.3. Si se han extraído facturas en la búsqueda global, se añaden a la lista total y se registra el éxito en el log. 
                if facturas_globales:
                    facturas_totales.extend(facturas_globales)
                    escribir_log(f"{'='*80}", mostrar_tiempo=False)
                    escribir_log(f"[OK] Búsqueda global finalizada: {len(facturas_globales)} facturas extraídas.\n{'='*80}")
                
                # C.B.4. Si no se han encontrado facturas en la búsqueda global, se registra esta situación en el log.
                else:
                    escribir_log(f"{'='*80}", mostrar_tiempo=False)
                    escribir_log(f"[INFO] No se encontraron facturas en el rango {fecha_desde} - {fecha_hasta}.\n{'='*80}")

            # C.B.5. Si ocurre cualquier error durante el proceso de búsqueda o extracción en el modo global, se captura la excepción, se registra el error en el log con detalles del mismo, se añade un registro de error a la lista total de facturas indicando que el error ocurrió en la búsqueda global, y se continúa con el proceso de cierre del navegador y finalización del proceso sin detenerlo completamente.
            except Exception as e:
                registro_vacio = FacturaEndesa(cup=cup_actual, 
                                                       error_RPA=False,  
                                                       msg_error_RPA=f"Sin facturas emitidas en el periodo ({fecha_desde} - {fecha_hasta}). ERROR en búsqueda global: {str(e)[:1000]}")
                facturas_totales.append(registro_vacio)
                escribir_log(f"[ERROR] Fallo crítico en la búsqueda global: {str(e)}")


        # D. Finalización del proceso, registro de resultados y cierre de navegador
        escribir_log(f"{'='*80}", pretexto="\n\n", mostrar_tiempo=False)
        escribir_log(f"[OK][FIN] Proceso RPA completado.\n\t\tTotal facturas extraídas: {len(facturas_totales)}\n{'='*80}")
        return facturas_totales

    # E. Manejo de errores críticos a nivel de proceso completo: Si ocurre cualquier excepción no manejada durante el proceso completo, se captura aquí, se registra el error crítico en el log con detalles del mismo, y se relanza la excepción para que pueda ser manejada por el llamador o para que detenga el proceso si es necesario.
    except Exception as e:
        escribir_log(f"[ERROR] FALLO CRÍTICO EN EL ROBOT: {e}")
        raise e

    # F. Asegurar el cierre del navegador y liberación de recursos: Independientemente de si el proceso se completa con éxito o si ocurre un error, se garantiza que el navegador se cerrará correctamente y que los recursos asociados se liberarán, registrando esta acción en el log.
    finally:
        if hasattr(robot, 'browser') and robot.browser:
            await robot.cerrar()
            escribir_log("[SISTEMA] Navegador cerrado y recursos liberados.\n\n")


# === ROBOT ENEL ===
async def ejecutar_robot_enel(fecha_desde: str, fecha_hasta: str) -> list[FacturaEnel]:
    robot = NavegadorAsync()
    facturas_totales = []
    login_successful = False
    
    try:
        # A. Inicio del proceso y Login

        escribir_log(f"    [INICIO] Iniciando proceso RPA-ENEL. \n\n{'='*40} ",pretexto="\n",mostrar_tiempo=False)
        
        for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
            escribir_log(f"[LOGIN] Intento {attempt}/{MAX_LOGIN_ATTEMPTS}...",pretexto="\n\t")

            # A.1. Iniciar el navegador y acceder a la URL de login
            await robot.iniciar()
            await robot.goto_url(URL_LOGIN_ENEL)
            
            # A.2. Intentar iniciar sesión con las credenciales proporcionadas
            login_successful = await _iniciar_sesion_enel(robot.get_page(), USER_ENEL, PASSWORD_ENEL)

            # A.3. Verificar si el login fue exitoso y en caso afirmativo, salir del bucle de intentos
            if login_successful:
                escribir_log(f"[LOGIN] Sesión establecida correctamente.")
                break
            
            # A.4. Si el login falla, cerrar el navegador y esperar antes de intentar de nuevo
            escribir_log(f"[ADVERTENCIA] Intento de login {attempt} fallido. Cerrando contexto.")
            await robot.cerrar()

            # A.5. Si no se ha logrado el login tras todos los intentos, lanzar una excepción crítica
            if attempt < MAX_LOGIN_ATTEMPTS:
                await asyncio.sleep(5)
            else:
                raise Exception(f"Fallo crítico: No se pudo acceder al portal tras {MAX_LOGIN_ATTEMPTS} intentos.")

        # B. Una vez logueados, obtenemos los roles disponibles 
        page = robot.get_page()
        escribir_log(f"[ROLES]")
        roles = await _obtener_todos_los_roles(page)

            # B.1. Si no se han podido obtener roles, esto indica un posible cambio en la estructura de la página o un fallo en el login, por lo que se registra un error crítico en el log y se lanza una excepción para detener el proceso, ya que sin los roles no se puede continuar con la extracción de facturas.
        if not roles:
            escribir_log(f"    -> [ERROR] No se pudieron obtener los roles disponibles para el usuario. Verifique que el login fue exitoso y que el formato de la página no ha cambiado.")
            raise Exception("No se pudieron obtener los roles disponibles para el usuario.")
        
        # C. PROCESAMIENTO DE FACTURAS POR ROL
        escribir_log(f"{'='*80}", pretexto="\n", mostrar_tiempo=False)
        escribir_log(f"PROCESANDO BUSQUEDA GLOBAL: Todos los roles disponibles\n{'='*80}")
        for irol, rol in enumerate(roles):
            
            escribir_log(f"\n\n[ROL {irol+1} / {len(roles)}]  ({rol.upper()})\n\t\t{'='*40}",mostrar_tiempo=False)
            
            try:
                # C.1. Seleccionar el rol actual para cargar las facturas asociadas a ese rol
                await _seleccionar_rol_especifico(page, rol)
                
                # C.2. Rellenar los filtros de fecha 
                escribir_log(f"[BUSQUEDA]")
                exito_busqueda = await _aplicar_filtros_fechas(page, fecha_desde, fecha_hasta)
                if not exito_busqueda:
                    continue

                #input(f"DEBUG: Filtros aplicados para el rol '{rol}'. Presiona Enter para continuar con la extracción de facturas para este rol...")
                # C.3. Extraer los datos de la tabla de resultados para el rol actual, y añadirlos a la lista total de facturas.
                escribir_log(f"[EXTRACCIÓN]")
                facturas_rol = await _extraer_tabla_facturas_enel(page, len(facturas_totales))
                
                # C.4. Si se han extraído facturas para el rol actual, se añaden a la lista total y se registra el éxito en el log.
                if facturas_rol and len(facturas_rol) > 0:
                    facturas_totales.extend(facturas_rol)
                    escribir_log(f"\n{'='*40}", mostrar_tiempo=False)
                    escribir_log(f"\t[OK] Búsqueda para rol {rol}: {len(facturas_rol)} facturas extraídas.\n{'='*40}", mostrar_tiempo=False)

                # C.5. Si no se han encontrado facturas para el rol actual, se registra esta situación en el log.
                else:
                    escribir_log(f"    [INFO] No hay facturas para el rol '{rol}' en el rango {fecha_desde} - {fecha_hasta}.\n\t\t{'='*40}")
                    continue

            # C.B.5. Si ocurre cualquier error durante el proceso de búsqueda o extracción, se captura la excepción, se registra el error en el log con detalles del mismo, se añade un registro de error a la lista total de facturas indicando que el error ocurrió en la búsqueda global, y se continúa con el proceso de cierre del navegador y finalización del proceso sin detenerlo completamente.
            except Exception as e:
                error_detalle = str(e)
                registro_error = FacturaEnel(cup="N/A", 
                                                error_RPA=True, 
                                                msg_error_RPA=f"ERROR en rol {rol}: {error_detalle[:1000]}")
                facturas_totales.append(registro_error)
                
                escribir_log(f"[ERROR] Fallo al procesar el rol {rol}. Detalles del error: \n\t\t{error_detalle}\n\t\t{'='*40}")
                continue
        
        # D. Finalización del proceso, registro de resultados y cierre de navegador
        escribir_log(f"{'='*80}", pretexto="\n\n", mostrar_tiempo=False)
        escribir_log(f"[OK][FIN] Proceso RPA completado.\n\t\tTotal facturas extraídas: {len(facturas_totales)}\n{'='*80}")
        return facturas_totales

    # E. Manejo de errores críticos a nivel de proceso completo: Si ocurre cualquier excepción no manejada durante el proceso completo, se captura aquí, se registra el error crítico en el log con detalles del mismo, y se relanza la excepción para que pueda ser manejada por el llamador o para que detenga el proceso si es necesario.
    except Exception as e:
        escribir_log(f"[ERROR] FALLO CRÍTICO EN EL ROBOT: {e}")
        raise e
    
    # F. Asegurar el cierre del navegador y liberación de recursos: Independientemente de si el proceso se completa con éxito o si ocurre un error, se garantiza que el navegador se cerrará correctamente y que los recursos asociados se liberarán, registrando esta acción en el log.
    finally:
        await robot.cerrar()
        escribir_log("[SISTEMA] Navegador cerrado.\n")




if __name__ == "__main__":
    asyncio.run(ejecutar_robot_endesa("01/10/2025","31/10/2025"))
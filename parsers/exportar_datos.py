import csv
import os

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
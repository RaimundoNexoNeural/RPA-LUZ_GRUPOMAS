from pydantic import BaseModel
from typing import Optional

### FACTURA ENDESA ###
class FacturaEndesa(BaseModel):
    """
    Clase para representar la estructura de datos de una factura de Endesa para clientes.
    Se utiliza Pydantic para la validación y serialización automática en FastAPI.
    """

    # === 0. ERRORES ===
    error_RPA: Optional[bool] = False
    msg_error_RPA: Optional[str] = ""
    
    # === 1. Metadata extraída directamente de la TABLA de Endesa ===
       
        # Identificadores
    cup: str
    numero_factura: Optional[str] = "N/A"
    contrato: Optional[str] = "N/A"
        # Fechas
    fecha_emision: Optional[str] = "N/A"
    fecha_inicio_periodo: Optional[str] = "N/A"
    fecha_fin_periodo: Optional[str] = "N/A"
        # Importes y estados
    importe_total: Optional[float] = 0.0
    secuencial: Optional[str] = "N/A"
    estado_factura: Optional[str] = "N/A"
    fraccionamiento: Optional[str] = "N/A"
    tipo_factura: Optional[str] = "N/A"


    # === 2. Selectores de Descarga (Para el proceso RPA) ===

    descarga_selector: Optional[str] = "N/A"
    
    # === 3. Datos DETALLADOS extraídos del XML/PDF ===
    
    # Campos generales
    mes_facturado: Optional[str] = None
    tarifa: Optional[str] = None
    direccion_suministro: Optional[str] = None

    num_dias: Optional[int] = None 

    # Datos de Potencia (€)
    potencia_p1: Optional[float] = 0.0
    potencia_p2: Optional[float] = 0.0
    potencia_p3: Optional[float] = 0.0
    potencia_p4: Optional[float] = 0.0
    potencia_p5: Optional[float] = 0.0
    potencia_p6: Optional[float] = 0.0 
        # Sumatorio de pontencia_p{i} (€)
    importe_de_potencia: Optional[float] = 0.0

    # Datos de Consumo (kWh)
    consumo_kw_p1: Optional[float] = 0.0
    consumo_kw_p2: Optional[float] = 0.0
    consumo_kw_p3: Optional[float] = 0.0
    consumo_kw_p4: Optional[float] = 0.0
    consumo_kw_p5: Optional[float] = 0.0
    consumo_kw_p6: Optional[float] = 0.0
        # Sumatorio de consumo_kw_p{i} (kWh)
    kw_totales: Optional[float] = 0.0 

    # Datos de Consumo (€)
    importe_consumo_p1: Optional[float] = 0.0
    importe_consumo_p2: Optional[float] = 0.0
    importe_consumo_p3: Optional[float] = 0.0
    importe_consumo_p4: Optional[float] = 0.0
    importe_consumo_p5: Optional[float] = 0.0
    importe_consumo_p6: Optional[float] = 0.0
    # Precios indexados de energía (€)
    energia_precio_indexado_p1: Optional[float] = 0.0
    energia_precio_indexado_p2: Optional[float] = 0.0
    energia_precio_indexado_p3: Optional[float] = 0.0
    energia_precio_indexado_p4: Optional[float] = 0.0
    energia_precio_indexado_p5: Optional[float] = 0.0
    energia_precio_indexado_p6: Optional[float] = 0.0
        # Sumatorio de importe_consumo_p{i} + energia_precio_indexado_p{i} (€)
    importe_consumo: Optional[float] = 0.0
    
    # Otros conceptos (€)
    importe_impuesto_electrico: Optional[float] = 0.0

    importe_bono_social: Optional[float] = 0.0
    importe_alquiler_equipos: Optional[float] = 0.0
    importe_reactiva: Optional[float] = 0.0
    importe_regularización_eficiencia_energetica: Optional[float] = 0.0
        # Sumatorio de importe_alquiler_equipos + importe_bono_social + complemento por energía_reactiva + importe_regularización_eficiencia_energetica
    importe_otros_conceptos: Optional[float] = 0.0

    # Excesos de Potencia (€)
    importe_exceso_potencia_p1: Optional[float] = 0.0
    importe_exceso_potencia_p2: Optional[float] = 0.0
    importe_exceso_potencia_p3: Optional[float] = 0.0
    importe_exceso_potencia_p4: Optional[float] = 0.0
    importe_exceso_potencia_p5: Optional[float] = 0.0
    importe_exceso_potencia_p6: Optional[float] = 0.0
        # Sumatorio de importe_exceso_potencia_p{i} (€)
    importe_exceso_potencia: Optional[float] = 0.0
    
    # Importe base imponible (€)
    importe_base_imponible: Optional[float] = 0.0
    
    # Importe facturado (€)
    importe_facturado: Optional[float] = 0.0

    # Fechas cobro (date)
    fecha_de_factura: Optional[str] = None
    fecha_de_vencimiento: Optional[str] = None


    def to_serializable_dict(self):
        """
        Convierte el objeto FacturaEndesaCliente en un diccionario serializable en JSON.
        """
        return self.dict()


### FACTURA ENEL ###  
class FacturaEnel(BaseModel):
    """
    Clase para representar la estructura de datos de una factura de Endesa para distribución.
    Se utiliza Pydantic para la validación y serialización automática en FastAPI.
    """

    # === 0. ERRORES ===
    error_RPA: Optional[bool] = False
    msg_error_RPA: Optional[str] = ""

    # === 1. Metadata extraída directamente de la TABLA de Endesa ===

        # Identificadores
    cup: str 
    numero_factura: Optional[str] = "N/A"
    contrato: Optional[str] = "N/A"
    direccion_suministro: Optional[str] = None
        # Fechas
    fecha_emision: Optional[str] = "N/A"
    fecha_inicio_periodo: Optional[str] = "N/A"
    fecha_fin_periodo: Optional[str] = "N/A"
        # Importes y estados
    estado_factura: Optional[str] = "N/A"
    importe_total: Optional[float] = 0.0
    tipo_factura: Optional[str] = "N/A"

    
    # === 2. Enlaces/Selectores de Descarga (Para el proceso RPA) ===
    
    descarga_selector: Optional[str] = "N/A"
    
    # === 3. Datos DETALLADOS extraídos del PDF ===
    
    # Campos generales
    mes_facturado: Optional[str] = None
    tarifa: Optional[str] = None
    num_dias: Optional[int] = None

    # Datos de Potencia Contratada (?)
    potencia_p1: Optional[float] = 0.0
    potencia_p2: Optional[float] = 0.0
    potencia_p3: Optional[float] = 0.0
    potencia_p4: Optional[float] = 0.0
    potencia_p5: Optional[float] = 0.0
    potencia_p6: Optional[float] = 0.0
    

    # Datos de Importe Potencia (€)
    termino_de_potencia_peaje: Optional[float] = 0.0
    termino_de_potencia_cargos: Optional[float] = 0.0
        # Sumatorio termino_de_potencia_peaje + termino_de_potencia_cargos (€)
    importe_de_potencia: Optional[float] = 0.0
    

    # Datos de Importe ATR (€)
    termino_de_energia_peaje: Optional[float] = 0.0
    termino_de_energia_cargos: Optional[float] = 0.0
        # Sumatorio termino_de_energia_peaje + termino_de_energia_cargos (€)
    importe_atr: Optional[float] = 0.0

    # Importe Exceso Potencia (€)
    importe_exceso_potencia: Optional[float] = 0.0

        # Subtotal (€) 
        # Sumatorio de importe_de_potencia + importe_atr + importe_exceso_potencia (€)
    importe_subtotal: Optional[float] = 0.0
    
    # Otros conceptos (€)
    importe_impuesto_electrico: Optional[float] = 0.0
    importe_alquiler_equipos: Optional[float] = 0.0
       
        # ? ? ? 
    importe_otros_conceptos: Optional[float] = 0.0
        # ? ? ?
    importe_reactiva: Optional[float] = 0.0
    
    # Importe base imponible (€)
    importe_base_imponible: Optional[float] = 0.0
    
    # Totales y fechas de pago
    importe_facturado: Optional[float] = 0.0
    
    # Fechas cobro (date)
    fecha_factura: Optional[str] = None
    fecha_de_vencimiento: Optional[str] = None
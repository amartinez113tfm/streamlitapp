# core/model_configs.py

# Mapeo extraído de la captura de pantalla
# Estructura: CODIGO: {"nombre": "Nombre", "contaminantes": ["LISTA"]}
ESTACIONES_MADRID = {
    4: {"nombre": "Plaza de España", "contaminantes": ["NO2"]},
    8: {"nombre": "Escuelas Aguirre", "contaminantes": ["NO2", "PM10", "PM2_5", "O3"]},
    16: {"nombre": "Arturo Soria", "contaminantes": ["NO2", "O3"]},
    18: {"nombre": "Farolillo", "contaminantes": ["NO2", "PM10", "O3"]},
    24: {"nombre": "Casa de Campo", "contaminantes": ["NO2", "PM10", "PM2_5", "O3"]},
    35: {"nombre": "Plaza del Carmen", "contaminantes": ["NO2", "O3"]},
    36: {"nombre": "Moratalaz", "contaminantes": ["NO2", "PM10"]},
    38: {"nombre": "Cuatro Caminos", "contaminantes": ["NO2", "PM10", "PM2_5"]},
    39: {"nombre": "Barrio del Pilar", "contaminantes": ["NO2", "O3"]},
    54: {"nombre": "Ensanche de Vallecas", "contaminantes": ["NO2", "O3"]},
    56: {"nombre": "Plaza Elíptica", "contaminantes": ["NO2", "PM10", "PM2_5"]},
    58: {"nombre": "El Pardo", "contaminantes": ["NO2", "O3"]},
    59: {"nombre": "Juan Carlos I", "contaminantes": ["NO2", "O3"]}
}

# Lista global de contaminantes para los selectores
CONTAMINANTES_DISPONIBLES = ["NO2", "PM10", "PM2_5", "O3"]
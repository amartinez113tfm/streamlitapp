
# Diccionario con las coordenadas reales de las estaciones de Madrid
DICC_ESTACIONES = {
    4:  {"nombre": "Plaza de España", "lat": 40.423853, "lon": -3.712257},
    8:  {"nombre": "Escuelas Aguirre", "lat": 40.421553, "lon": -3.682319},
    16:  {"nombre": "Arturo Soria", "lat": 40.3947, "lon": -3.7318},
    18: {"nombre": "Farolillo", "lat": 40.419358, "lon": -3.747347},
    24: {"nombre": "Casa de Campo", "lat": 40.419358, "lon": -3.747347},
    35: {"nombre": "Plaza del Carmen", "lat": 40.419208, "lon": -3.703164},
    36: {"nombre": "Moratalaz", "lat": 40.407983, "lon": -3.645314},
    38: {"nombre": "Cuatro Caminos", "lat": 40.445544, "lon": -3.707131},
    39: {"nombre": "Barrio del Pilar", "lat": 40.478233, "lon": -3.711542},
    54: {"nombre": "Ensanche de Vallecas", "lat": 40.372833, "lon": -3.616342},
    56: {"nombre": "Plaza Elíptica", "lat": 40.385039, "lon": -3.718692},
    58: {"nombre": "El Pardo", "lat": 40.521822, "lon": -3.774536},
    59: {"nombre": "Juan Carlos I", "lat": 40.465250, "lon": -3.610514}
}



# 1. Definimos umbrales legales (Ejemplo NO2 según normativa europea/Madrid)
UMBRALES = {"no2": 40, "pm10": 50, "pm2_5": 25, "so2": 125, "o3":120}


# 1. Diccionario de estaciones
mapa_estaciones_O3 = {
    "Escuelas Aguirre": "8",
    "Arturo Soria": "16",
    "Farolillo": "18",
    "Casa de Campo": "24",
    "Plaza del Carmen": "35",
    "Barrio del Pilar": "39",
    "Ensanche de Vallecas": "54",
    "El Pardo": "58",
    "Juan Carlos I": "59"
}

mapa_estaciones_NO2 = {
  "Plaza de España": "4",
  "Escuelas Aguirre": "8",
  "Arturo Soria": "16",
  "Farolillo": "18",
  "Casa de Campo": "24",
  "Plaza del Carmen": "35",
  "Moratalaz": "36",
  "Cuatro Caminos": "38",
  "Barrio del Pilar": "39",
  "Ensanche de Vallecas": "54",
  "Plaza Elíptica": "56",
  "El Pardo": "58",
  "Juan Carlos I": "59"
}
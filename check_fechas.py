from core import data_manager as dm
import datetime

def check_fechas():
    db = dm.get_db_connectionTrafico()
    col = db['trafico_unificado']

    # Buscamos el documento más antiguo y el más reciente
    primero = col.find_one(sort=[("timestamp", 1)])
    ultimo = col.find_one(sort=[("timestamp", -1)])

    print(f"📊 Rango de datos en 'trafico_unificado':")
    print(f"📅 Desde: {primero['timestamp'] if primero else 'N/A'}")
    print(f"📅 Hasta: {ultimo['timestamp'] if ultimo else 'N/A'}")

    # Comprobar si hay algo específico en junio 2025
    conteo_junio = col.count_documents({
        "timestamp": {
            "$gte": datetime.datetime(2025, 6, 1),
            "$lt": datetime.datetime(2025, 7, 1)
        }
    })
    print(f"🔎 Documentos en junio 2025: {conteo_junio}")


if __name__ == "__main__":
    check_fechas()
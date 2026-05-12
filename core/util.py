import pandas as pd
import streamlit as st
from pymongo import MongoClient
from core import model_configs as mc
from datetime import datetime, time
from pandas import json_normalize



def get_mongodb_client():
    """Crea un único cliente para toda la aplicación con timeouts de seguridad."""
    MONGO_URI = st.secrets["MONGO_URI"]
    # Añadimos parámetros para evitar el DNS Timeout
    return MongoClient(
        MONGO_URI,
        connectTimeoutMS=30000,
        serverSelectionTimeoutMS=30000,
        connect=False  # No conecta hasta la primera consulta real
    )

def get_db_connection(db_name='madrid_aire'):
    """Retorna la base de datos solicitada usando el cliente único."""
    client = get_mongodb_client()
    return client[db_name]

# Reemplazamos tu antigua función por un alias para no romper el resto del código
def get_db_connectionTrafico():
    return get_db_connection('trafico_madrid')


def unificar_trafico():
    db = get_db_connectionTrafico()
    nueva_col = db['trafico_unificado']
    
    # 1. Migrar Histórico (Esquema viejo)
    # Suponiendo que el viejo tenía 'estacion' y 'valor'
    for doc in db['trafico_historico'].find():
        doc_unificado = {
            "estacion_id": str(doc.get('estacion')), # Estandarizamos a estacion_id
            "timestamp": doc.get('timestamp'),
            "intensidad": doc.get('valor', 0), # Estandarizamos a intensidad
            "tipo": "historico"
        }
        nueva_col.insert_one(doc_unificado)

    # 2. Migrar Predicciones (Esquema nuevo)
    for doc in db['predicciones_horarias'].find():
        doc_unificado = {
            "estacion_id": str(doc.get('estacion')),
            "timestamp": doc.get('timestamp'),
            "intensidad": doc.get('valor', 0),
            "tipo": "prediccion"
        }
        nueva_col.insert_one(doc_unificado)
    
    # 3. Crear índices para que vuele
    nueva_col.create_index([("estacion_id", 1), ("timestamp", 1)])


unificar_trafico()
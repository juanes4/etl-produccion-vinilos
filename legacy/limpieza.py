"""Versión anterior (reemplazada por el paquete etl/). Se conserva como referencia.

Pasa de una fila por turno con 18 columnas "Codigo N en horas" a una fila por paro.
Ejecutar desde la raíz del repo:  python legacy/limpieza.py
"""
from pathlib import Path

import pandas as pd

DATOS = Path(__file__).resolve().parent.parent / "data" / "raw"

mapa_paros = {
    "Codigo 1 en horas": "[01] Falla del sistema electromecánico y/o de control",
    "Codigo 2 en horas": "[02] Espera de soporte de mantenimiento",
    "Codigo 3 en horas": "[03] Novedad en los sistemas de potencia (Aire, energía, vapor)",
    "Codigo 4 en horas": "[04] Mantenimiento preventivo",
    "Codigo 5 en horas": "[05] Ajuste operativo",
    "Codigo 6 en horas": "[06] Limpieza por derrame operativo",
    "Codigo 7 en horas": "[07] Alistamiento de máquina / Cambio de referencia",
    "Codigo 8 en horas": "[08] Capacitación / Reunión",
    "Codigo 9 en horas": "[09] Falta de operario",
    "Codigo 10 en horas": "[10] Paro por ventaja/evacuación",
    "Codigo 11 en horas": "[11] Reproceso",
    "Codigo 12 en horas": "[12] Materia prima defectuosa",
    "Codigo 13 en horas": "[13] En espera por el aval del laboratorio de microbiología",
    "Codigo 14 en horas": "[14] Falta de materia prima",
    "Codigo 15 en horas": "[15] Cambio de insumos (Roscadores, O'ring, Etiquetas)",
    "Codigo 16 en horas": "[16] Alimentación y aseo de la zona de trabajo y la máquina",
    "Codigo 17 en horas": "[17] Pausa activa",
    "Codigo 18 en horas": "[18] Desinfeccion"
}


df = pd.read_excel(DATOS / "data_base.xlsx")

columnas_horas = [col for col in df.columns if "en horas" in col]

filas_transformadas = []

for _, fila in df.iterrows():
    primera_fila = True  
    for col in columnas_horas:
        horas = fila[col]
        if pd.notna(horas) and horas != 0:

            nueva_fila = fila.copy()
            nueva_fila["Tipo de Paro"] = mapa_paros[col]
            nueva_fila["Horas Paro"] = horas

            if not primera_fila:
                nueva_fila["Pacas producidas"] = 0
                nueva_fila["Horas trabajadas"] = 0

            filas_transformadas.append(nueva_fila)

            primera_fila = False


df_final = pd.DataFrame(filas_transformadas)

df_final.to_excel(DATOS / "data_base_transformado.xlsx", index=False)

print("Archivo generado: data/raw/data_base_transformado.xlsx")

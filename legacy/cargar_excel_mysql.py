"""Versión anterior (reemplazada por el paquete etl/). Se conserva como referencia.

Sincronizaba fila a fila contra un esquema plano (registros, maquinas, operarios...).
Ejecutar desde la raíz del repo:  python legacy/cargar_excel_mysql.py
"""
import os
from pathlib import Path

import pandas as pd
import mysql.connector


conn = mysql.connector.connect(
    host="localhost",
    user=os.environ.get("MYSQL_USER", "root"),
    password=os.environ["MYSQL_PASSWORD"],
    database="temperas_vinilos"
)

cursor = conn.cursor()


df = pd.read_excel(Path(__file__).resolve().parent.parent / "data" / "raw" / "data_base_transformado.xlsx")

columnas_texto = ["Maquina", "Operario", "Referencia", "Turno", "Tipo de Paro"]
df[columnas_texto] = df[columnas_texto].fillna("")

columnas_numericas = ["Pacas producidas", "Horas trabajadas", "Horas Paro"]
df[columnas_numericas] = df[columnas_numericas].fillna(0)


def insert_unique(table, column, value):
    cursor.execute(f"SELECT id FROM {table} WHERE {column}=%s", (value,))
    result = cursor.fetchone()

    if result:
        return result[0]
    
    cursor.execute(
        f"INSERT INTO {table} ({column}) VALUES (%s)",
        (value,)
    )
    conn.commit()
    return cursor.lastrowid

def buscar_registro_existente(row):
    cursor.execute("""
        SELECT r.id FROM registros r
        JOIN maquinas m ON r.maquina_id = m.id
        JOIN operarios o ON r.operario_id = o.id
        JOIN tipos_paro t ON r.tipo_paro_id = t.id
        WHERE r.fecha=%s AND m.nombre=%s AND o.nombre=%s
          AND r.referencia=%s AND t.nombre=%s
    """, (
        row["Fecha"], row["Maquina"], row["Operario"],
        row["Referencia"], row["Tipo de Paro"]
    ))

    result = cursor.fetchone()
    return result[0] if result else None


cursor.execute("""
    SELECT r.id, r.fecha, m.nombre, o.nombre, r.referencia, t.nombre
    FROM registros r
    JOIN maquinas m ON r.maquina_id = m.id
    JOIN operarios o ON r.operario_id = o.id
    JOIN tipos_paro t ON r.tipo_paro_id = t.id
""")

registros_mysql = cursor.fetchall()


claves_mysql = set(
    (fila[1], fila[2], fila[3], fila[4], fila[5])
    for fila in registros_mysql
)


claves_excel = set(
    (row["Fecha"], row["Maquina"], row["Operario"], row["Referencia"], row["Tipo de Paro"])
    for _, row in df.iterrows()
)


claves_a_eliminar = claves_mysql - claves_excel

for clave in claves_a_eliminar:
    cursor.execute("""
        DELETE r FROM registros r
        JOIN maquinas m ON r.maquina_id = m.id
        JOIN operarios o ON r.operario_id = o.id
        JOIN tipos_paro t ON r.tipo_paro_id = t.id
        WHERE r.fecha=%s AND m.nombre=%s AND o.nombre=%s
          AND r.referencia=%s AND t.nombre=%s
    """, clave)

    print(f"ELIMINADO: {clave}")



for _, row in df.iterrows():

    maquina_id = insert_unique("maquinas", "nombre", row["Maquina"])
    operario_id = insert_unique("operarios", "nombre", row["Operario"])
    tipo_paro_id = insert_unique("tipos_paro", "nombre", row["Tipo de Paro"])
    turno_id = insert_unique("turnos", "nombre", row["Turno"])

    registro_id = buscar_registro_existente(row)

    if registro_id is None:

        cursor.execute("""
            INSERT INTO registros (
                fecha, maquina_id, operario_id, referencia,
                pacas_producidas, horas_trabajadas, turno_id,
                tipo_paro_id, horas_paro
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            row["Fecha"], maquina_id, operario_id, row["Referencia"],
            row["Pacas producidas"], row["Horas trabajadas"],
            turno_id, tipo_paro_id, row["Horas Paro"]
        ))

        print(f"INSERTADO: {row['Maquina']} - {row['Tipo de Paro']}")

    else:

        cursor.execute("""
            UPDATE registros
            SET pacas_producidas=%s,
                horas_trabajadas=%s,
                horas_paro=%s,
                turno_id=%s,
                maquina_id=%s,
                operario_id=%s
            WHERE id=%s
        """, (
            row["Pacas producidas"],
            row["Horas trabajadas"],
            row["Horas Paro"],
            turno_id,
            maquina_id,
            operario_id,
            registro_id
        ))

        print(f"ACTUALIZADO: {row['Maquina']} - {row['Tipo de Paro']}")

conn.commit()
conn.close()

print("\nSINCRONIZACIÓN COMPLETADA (Insertar + Actualizar + Eliminar).")

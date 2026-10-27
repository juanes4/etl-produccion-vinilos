"""Carga a MySQL.

- Las dimensiones se actualizan con upsert, así sus ids no cambian entre corridas.
- Los hechos se reemplazan completos dentro de UNA transacción: si algo falla se
  hace rollback y los dashboards siguen viendo la última carga buena. Esto también
  refleja filas que se corrigieron o borraron en el Excel.
"""

import json
import logging
from datetime import datetime

import mysql.connector
import pandas as pd

from .catalogos import PAROS
from .config import RAIZ_PROYECTO, Config
from .transformar import Resultado

log = logging.getLogger(__name__)

SCRIPTS_ESQUEMA = ("01_esquema.sql", "02_vistas.sql")
TAMANO_LOTE = 1000
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def conectar(cfg: Config):
    return mysql.connector.connect(
        host=cfg.mysql_host,
        port=cfg.mysql_puerto,
        user=cfg.mysql_usuario,
        password=cfg.mysql_password,
        database=cfg.mysql_base_datos,
        charset="utf8mb4",
        autocommit=False,
    )


def _sentencias(texto: str) -> list[str]:
    lineas = [l for l in texto.splitlines() if not l.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lineas).split(";") if s.strip()]


def asegurar_esquema(conn) -> None:
    """Crea tablas y vistas si no existen (los scripts son idempotentes)."""
    cur = conn.cursor()
    for nombre in SCRIPTS_ESQUEMA:
        for sentencia in _sentencias((RAIZ_PROYECTO / "sql" / nombre).read_text(encoding="utf-8")):
            cur.execute(sentencia)
    cur.close()


def ultimo_hash_exitoso(conn) -> str | None:
    cur = conn.cursor()
    cur.execute(
        "SELECT hash_archivo FROM etl_ejecuciones WHERE estado = 'EXITO' "
        "ORDER BY id_ejecucion DESC LIMIT 1"
    )
    fila = cur.fetchone()
    cur.close()
    return fila[0] if fila else None


def registrar_ejecucion(conn, inicio: datetime, estado: str, archivo: str,
                        huella: str | None, res: Resultado | None = None,
                        mensaje: str | None = None) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO etl_ejecuciones (inicio, fin, estado, archivo, hash_archivo, filas_leidas, "
        "registros, paros, calidad, mensaje) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            inicio, datetime.now(), estado, archivo, huella,
            res.calidad["filas_leidas"] if res else None,
            len(res.registros) if res else None,
            len(res.paros) if res else None,
            json.dumps(res.calidad, ensure_ascii=False) if res else None,
            mensaje,
        ),
    )
    conn.commit()
    cur.close()


def _filas(df: pd.DataFrame) -> list[tuple]:
    """DataFrame -> tuplas con tipos nativos de Python y None en lugar de NaN."""
    return list(df.astype(object).where(df.notna(), None).itertuples(index=False, name=None))


def _insertar(cur, sql: str, filas: list[tuple]) -> None:
    for i in range(0, len(filas), TAMANO_LOTE):
        cur.executemany(sql, filas[i:i + TAMANO_LOTE])


def _mapa(cur, tabla: str, id_col: str, nombre_col: str) -> dict:
    cur.execute(f"SELECT {nombre_col}, {id_col} FROM {tabla}")
    return dict(cur.fetchall())


def _dim_fecha(fechas: pd.Series) -> pd.DataFrame:
    rango = pd.date_range(fechas.min(), fechas.max(), freq="D")
    return pd.DataFrame({
        "fecha": rango.date,
        "anio": rango.year,
        "trimestre": rango.quarter,
        "mes": rango.month,
        "nombre_mes": [MESES[m - 1] for m in rango.month],
        "semana_iso": rango.isocalendar().week.to_numpy(),
        "dia_semana": rango.dayofweek + 1,
        "nombre_dia": [DIAS[d] for d in rango.dayofweek],
        "es_fin_semana": (rango.dayofweek >= 5).astype(int),
    })


def cargar(conn, res: Resultado) -> None:
    r = res.registros
    cur = conn.cursor()
    # Con autocommit=False, la consulta del último hash deja abierta una transacción implícita.
    if conn.in_transaction:
        conn.commit()
    conn.start_transaction()
    try:
        # --- Dimensiones ---
        _insertar(cur, "INSERT INTO dim_paro (id_paro, descripcion, area_impacto, es_programado) "
                       "VALUES (%s, %s, %s, %s) AS n ON DUPLICATE KEY UPDATE "
                       "descripcion = n.descripcion, area_impacto = n.area_impacto, es_programado = n.es_programado",
                  [(c, d, a, int(p)) for c, (d, a, p) in PAROS.items()])
        _insertar(cur, "INSERT INTO dim_maquina (nombre) VALUES (%s) AS n ON DUPLICATE KEY UPDATE nombre = n.nombre",
                  [(v,) for v in sorted(r["maquina"].unique())])
        _insertar(cur, "INSERT INTO dim_operario (nombre) VALUES (%s) AS n ON DUPLICATE KEY UPDATE nombre = n.nombre",
                  [(v,) for v in sorted(r["operario"].unique())])
        _insertar(cur, "INSERT INTO dim_producto (referencia, linea, volumen_cc, num_colores) "
                       "VALUES (%s, %s, %s, %s) AS n ON DUPLICATE KEY UPDATE "
                       "linea = n.linea, volumen_cc = n.volumen_cc, num_colores = n.num_colores",
                  _filas(res.productos))
        _insertar(cur, "INSERT INTO dim_turno (nombre, hora_inicio, hora_fin, duracion_horas) "
                       "VALUES (%s, %s, %s, %s) AS n ON DUPLICATE KEY UPDATE "
                       "hora_inicio = n.hora_inicio, hora_fin = n.hora_fin, duracion_horas = n.duracion_horas",
                  _filas(res.turnos))
        _insertar(cur, "INSERT INTO dim_fecha (fecha, anio, trimestre, mes, nombre_mes, semana_iso, "
                       "dia_semana, nombre_dia, es_fin_semana) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                       "AS n ON DUPLICATE KEY UPDATE nombre_mes = n.nombre_mes, nombre_dia = n.nombre_dia",
                  _filas(_dim_fecha(r["fecha"])))

        # --- Hechos ---
        hechos = pd.DataFrame({
            "id_registro": r["id_registro"],
            "fila_excel": r["fila_excel"],
            "fecha": r["fecha"].dt.date,
            "id_maquina": r["maquina"].map(_mapa(cur, "dim_maquina", "id_maquina", "nombre")),
            "id_operario": r["operario"].map(_mapa(cur, "dim_operario", "id_operario", "nombre")),
            "id_producto": r["referencia"].map(_mapa(cur, "dim_producto", "id_producto", "referencia")),
            "id_turno": r["turno"].map(_mapa(cur, "dim_turno", "id_turno", "nombre")),
            "pacas_producidas": r["pacas"],
            "horas_trabajadas": r["horas_trabajadas"],
            "horas_paro": r["horas_paro"],
            "horas_paro_programado": r["horas_paro_programado"],
            "num_paros": r["num_paros"].astype(int),
            "es_atipico": r["es_atipico"].astype(int),
            "es_inconsistente": r["es_inconsistente"].astype(int),
        })
        sin_id = hechos[["id_maquina", "id_operario", "id_producto", "id_turno"]].isna().any(axis=1)
        if sin_id.any():
            raise RuntimeError(f"{sin_id.sum()} registros no encontraron su dimensión en MySQL")

        cur.execute("DELETE FROM fact_paro")
        cur.execute("DELETE FROM fact_produccion")
        _insertar(cur, "INSERT INTO fact_produccion (id_registro, fila_excel, fecha, id_maquina, id_operario, "
                       "id_producto, id_turno, pacas_producidas, horas_trabajadas, horas_paro, "
                       "horas_paro_programado, num_paros, es_atipico, es_inconsistente) "
                       "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                  _filas(hechos))
        _insertar(cur, "INSERT INTO fact_paro (id_registro, id_paro, horas_paro) VALUES (%s, %s, %s)",
                  _filas(res.paros[["id_registro", "id_paro", "horas_paro"]]))

        conn.commit()
        log.info("Cargados %d registros de producción y %d paros", len(hechos), len(res.paros))
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

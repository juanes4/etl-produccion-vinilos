"""Limpieza y modelado de los datos.

El Excel de origen trae UNA FILA POR PARO: la primera fila de cada turno tiene las
pacas y horas trabajadas reales y las siguientes filas del mismo turno las traen en 0.
Aquí se reconstruye cada turno ("registro") para separar:
  - registros: un renglón por turno de máquina (pacas, horas, totales de paro)
  - paros:     un renglón por (registro, código de paro) con las horas detenidas
Así las pacas no se duplican ni hay que sumarlas con filas en 0.
"""

import logging
import re
from dataclasses import dataclass

import pandas as pd

from .catalogos import CORRECCIONES_LINEA, NO_APLICA, OPERARIO_NO_APLICA, PAROS, SIN_REGISTRO

log = logging.getLogger(__name__)

# Encabezado en Excel -> nombre interno
COLUMNAS = {
    "Fecha": "fecha",
    "Maquina": "maquina",
    "Operario": "operario",
    "Referencia": "referencia",
    "Pacas producidas": "pacas",
    "Horas trabajadas": "horas_trabajadas",
    "Turno": "turno",
    "Tipo de Paro": "tipo_paro",
    "Horas Paro": "horas_paro",
}
CLAVE_REGISTRO = ["fecha", "maquina", "operario", "referencia", "turno"]

_HORA = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", re.IGNORECASE)
_PRODUCTO = re.compile(r"^(.*?)\s+(\d+)cc(?:\s*\((\d+) col\))?")


@dataclass
class Resultado:
    registros: pd.DataFrame
    paros: pd.DataFrame
    productos: pd.DataFrame
    turnos: pd.DataFrame
    calidad: dict


def limpiar_texto(serie: pd.Series, vacio: str = SIN_REGISTRO) -> pd.Series:
    """Quita espacios repetidos y reemplaza vacíos por un valor explícito."""
    s = serie.astype("string").str.split().str.join(" ")
    return s.replace("", pd.NA).fillna(vacio).astype(object)


def normalizar_referencia(ref: str) -> str:
    if ref in (SIN_REGISTRO, NO_APLICA):
        return ref
    s = re.sub(r"(\d+)\s*cc\b", r"\1cc", ref, flags=re.IGNORECASE)
    s = re.sub(r"\(\s*(\d+)\s*col\s*\)", r"(\1 col)", s, flags=re.IGNORECASE)
    s = re.sub(r"(\d+cc)\(", r"\1 (", s)
    for malo, bueno in CORRECCIONES_LINEA.items():
        if s.startswith(malo + " "):
            s = bueno + s[len(malo):]
    return s


def describir_producto(ref: str) -> tuple[str, int | None, int | None]:
    """'Torre 22cc (12 col)' -> ('Torre', 22, 12)."""
    m = _PRODUCTO.match(ref)
    if not m:
        return ref, None, None
    colores = int(m.group(3)) if m.group(3) else None
    return m.group(1), int(m.group(2)), colores


def describir_turno(nombre: str) -> tuple[str | None, str | None, float | None]:
    """'10pm-6am (Turno 3)' -> ('22:00:00', '06:00:00', 8.0)."""
    horas = _HORA.findall(nombre)
    if len(horas) < 2:
        return None, None, None

    def minutos(h, m, am_pm):
        return (int(h) % 12 + (12 if am_pm.lower() == "pm" else 0)) * 60 + int(m or 0)

    ini, fin = minutos(*horas[0]), minutos(*horas[1])
    duracion = (fin - ini) % (24 * 60)  # soporta turnos que cruzan la medianoche
    return f"{ini // 60:02d}:{ini % 60:02d}:00", f"{fin // 60:02d}:{fin % 60:02d}:00", round(duracion / 60, 2)


def codigo_paro(tipo: pd.Series) -> pd.Series:
    """'[05] Ajuste operativo' -> 5."""
    texto = tipo.astype("string")
    codigo = texto.str.extract(r"\[(\d+)\]", expand=False)
    codigo = codigo.fillna(texto.str.extract(r"^\s*(\d+)", expand=False))
    return pd.to_numeric(codigo, errors="coerce")


def reconstruir_registros(d: pd.DataFrame) -> pd.Series:
    """Asigna un id de registro (turno) a cada fila.

    Una fila es continuación del registro anterior si tiene la misma clave, su código
    de paro es mayor que el anterior (los códigos vienen en orden ascendente dentro
    de un turno) y trae pacas = 0 y horas trabajadas = 0.
    """
    clave = d[CLAVE_REGISTRO].astype(str).agg("|".join, axis=1)
    codigo = d["id_paro"].fillna(-1)
    continuacion = (
        clave.eq(clave.shift())
        & codigo.gt(codigo.shift())
        & d["pacas"].eq(0)
        & d["horas_trabajadas"].eq(0)
    )
    return (~continuacion).cumsum()


def _fuera_de_rango(serie: pd.Series, minimo: float, maximo: float) -> pd.Series:
    return serie.notna() & ((serie < minimo) | (serie > maximo))


def transformar(df: pd.DataFrame, max_pacas_por_hora: float) -> Resultado:
    faltantes = set(COLUMNAS) - set(df.columns)
    if faltantes:
        raise ValueError(f"Al Excel le faltan columnas: {sorted(faltantes)}")

    d = df[list(COLUMNAS)].rename(columns=COLUMNAS).copy()
    d["fila_excel"] = d.index + 2  # +1 por encabezado, +1 porque Excel empieza en 1
    calidad: dict = {"filas_leidas": len(d)}

    # --- Filas inutilizables ---
    d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce").dt.normalize()
    invalidas = d["fecha"].isna() | d["maquina"].isna()
    calidad["filas_descartadas_sin_fecha_o_maquina"] = int(invalidas.sum())
    d = d[~invalidas].reset_index(drop=True)

    # --- Textos ---
    d["maquina"] = limpiar_texto(d["maquina"])
    d["operario"] = limpiar_texto(d["operario"])
    d.loc[d["operario"].str.lower().isin(OPERARIO_NO_APLICA), "operario"] = NO_APLICA
    d["turno"] = limpiar_texto(d["turno"])
    ref_original = limpiar_texto(d["referencia"])
    d["referencia"] = ref_original.map(normalizar_referencia)
    calidad["referencias_corregidas"] = int((ref_original != d["referencia"]).sum())
    calidad["filas_sin_operario"] = int((d["operario"] == SIN_REGISTRO).sum())
    calidad["filas_sin_turno"] = int((d["turno"] == SIN_REGISTRO).sum())

    # --- Números ---
    for col in ("pacas", "horas_trabajadas", "horas_paro"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    for col, maximo in (("pacas", float("inf")), ("horas_trabajadas", 24), ("horas_paro", 24)):
        malos = _fuera_de_rango(d[col], 0, maximo)
        calidad[f"{col}_fuera_de_rango"] = int(malos.sum())
        d.loc[malos, col] = pd.NA

    # --- Códigos de paro ---
    d["id_paro"] = codigo_paro(d["tipo_paro"])
    desconocidos = d["id_paro"].notna() & ~d["id_paro"].isin(list(PAROS))
    calidad["codigos_paro_desconocidos"] = int(desconocidos.sum() + d["id_paro"].isna().sum())
    d.loc[desconocidos, "id_paro"] = pd.NA

    # --- Reconstrucción de turnos ---
    d["id_registro"] = reconstruir_registros(d)

    primeras = d.drop_duplicates("id_registro", keep="first")
    registros = primeras[["id_registro", "fila_excel", *CLAVE_REGISTRO, "pacas", "horas_trabajadas"]].copy()

    paros = (
        d[d["id_paro"].notna() & (d["horas_paro"] > 0)]
        .groupby(["id_registro", "id_paro"], as_index=False)["horas_paro"].sum()
    )
    paros["id_paro"] = paros["id_paro"].astype(int)
    paros["es_programado"] = paros["id_paro"].map(lambda c: PAROS[c][2])

    totales = paros.groupby("id_registro").agg(
        horas_paro=("horas_paro", "sum"), num_paros=("id_paro", "count")
    )
    programados = paros[paros["es_programado"]].groupby("id_registro")["horas_paro"].sum()
    registros = registros.join(totales, on="id_registro")
    registros["horas_paro_programado"] = registros["id_registro"].map(programados)
    registros[["horas_paro", "horas_paro_programado", "num_paros"]] = (
        registros[["horas_paro", "horas_paro_programado", "num_paros"]].fillna(0)
    )

    # --- Banderas de calidad (no se borran: se marcan y las vistas las excluyen) ---
    horas = registros["horas_trabajadas"]
    pacas_hora = registros["pacas"] / horas.where(horas > 0)
    registros["es_atipico"] = pacas_hora > max_pacas_por_hora
    registros["es_inconsistente"] = (horas > 0) & (registros["horas_paro"] > horas + 1e-6)

    calidad.update(
        registros=len(registros),
        paros=len(paros),
        registros_sin_pacas=int(registros["pacas"].isna().sum()),
        registros_atipicos=int(registros["es_atipico"].sum()),
        registros_paro_mayor_que_horas=int(registros["es_inconsistente"].sum()),
    )

    productos = pd.DataFrame({"referencia": sorted(registros["referencia"].unique())})
    productos[["linea", "volumen_cc", "num_colores"]] = productos["referencia"].map(describir_producto).tolist()

    turnos = pd.DataFrame({"nombre": sorted(registros["turno"].unique())})
    turnos[["hora_inicio", "hora_fin", "duracion_horas"]] = turnos["nombre"].map(describir_turno).tolist()

    for clave, valor in calidad.items():
        log.info("Calidad | %s: %s", clave, valor)

    return Resultado(registros.reset_index(drop=True), paros, productos, turnos, calidad)

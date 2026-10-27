"""Punto de entrada:  python -m etl [--forzar] [--simulacion] [--config ruta]"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .cargar import asegurar_esquema, cargar, conectar, registrar_ejecucion, ultimo_hash_exitoso
from .config import RAIZ_PROYECTO, leer_config
from .extraer import extraer, hash_archivo
from .transformar import Resultado, transformar

log = logging.getLogger("etl")


def configurar_logs(carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    archivo = RotatingFileHandler(carpeta / "etl.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    consola = logging.StreamHandler()
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    for handler in (archivo, consola):
        handler.setFormatter(formato)
        raiz.addHandler(handler)


def exportar_csv(res: Resultado, carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre in ("registros", "paros", "productos", "turnos"):
        getattr(res, nombre).to_csv(carpeta / f"{nombre}.csv", index=False, encoding="utf-8-sig")
    (carpeta / "calidad.json").write_text(json.dumps(res.calidad, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Simulación: tablas limpias exportadas a %s", carpeta)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m etl", description="ETL Excel -> MySQL de máquinas de vinilos")
    parser.add_argument("--config", default=str(RAIZ_PROYECTO / "config.ini"), help="ruta del archivo de configuración")
    parser.add_argument("--forzar", action="store_true", help="recargar aunque el Excel no haya cambiado")
    parser.add_argument("--simulacion", action="store_true", help="solo extraer y limpiar; exporta CSV sin tocar MySQL")
    args = parser.parse_args(argv)

    try:
        cfg = leer_config(Path(args.config))
    except Exception as e:
        print(f"Error de configuración: {e}", file=sys.stderr)
        return 2

    configurar_logs(cfg.carpeta_logs)
    inicio, t0 = datetime.now(), time.perf_counter()
    log.info("=== Inicio ETL (%s) ===", "simulación" if args.simulacion else "carga")

    if args.simulacion:
        try:
            res = transformar(extraer(cfg.archivo_excel, cfg.hoja), cfg.max_pacas_por_hora)
            exportar_csv(res, cfg.carpeta_salida)
            return 0
        except Exception:
            log.exception("La simulación falló")
            return 1

    conn = huella = res = None
    try:
        conn = conectar(cfg)
        asegurar_esquema(conn)

        huella = hash_archivo(cfg.archivo_excel)
        if not args.forzar and huella == ultimo_hash_exitoso(conn):
            log.info("El Excel no cambió desde la última carga exitosa; no se recarga (usa --forzar).")
            registrar_ejecucion(conn, inicio, "SIN_CAMBIOS", cfg.archivo_excel.name, huella)
            return 0

        res = transformar(extraer(cfg.archivo_excel, cfg.hoja), cfg.max_pacas_por_hora)
        cargar(conn, res)
        registrar_ejecucion(conn, inicio, "EXITO", cfg.archivo_excel.name, huella, res)
        log.info("=== ETL terminado en %.1f s ===", time.perf_counter() - t0)
        return 0
    except Exception as e:
        log.exception("El ETL falló: %s", e)
        if conn is not None and conn.is_connected():
            try:
                registrar_ejecucion(conn, inicio, "ERROR", cfg.archivo_excel.name, huella, res, str(e)[:5000])
            except Exception:
                log.exception("No se pudo registrar el error en etl_ejecuciones")
        return 1
    finally:
        if conn is not None and conn.is_connected():
            conn.close()

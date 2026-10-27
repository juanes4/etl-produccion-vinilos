import hashlib
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


def hash_archivo(ruta: Path) -> str:
    sha = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            sha.update(bloque)
    return sha.hexdigest()


def extraer(ruta: Path, hoja: str | int) -> pd.DataFrame:
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el Excel de origen: {ruta}")
    try:
        df = pd.read_excel(ruta, sheet_name=hoja)
    except PermissionError as e:
        raise PermissionError(
            f"No se pudo leer {ruta.name}. Si está abierto en Excel, ciérralo y vuelve a ejecutar."
        ) from e
    # Quita espacios/saltos de línea sobrantes en los encabezados.
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    log.info("Extraídas %d filas de %s (hoja %r)", len(df), ruta.name, hoja)
    return df

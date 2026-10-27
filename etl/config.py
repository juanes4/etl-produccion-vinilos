import configparser
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    archivo_excel: Path
    hoja: str | int
    mysql_host: str
    mysql_puerto: int
    mysql_usuario: str
    mysql_password: str
    mysql_base_datos: str
    max_pacas_por_hora: float
    carpeta_logs: Path
    carpeta_salida: Path


def _ruta(valor: str) -> Path:
    ruta = Path(valor)
    return ruta if ruta.is_absolute() else (RAIZ_PROYECTO / ruta).resolve()


def leer_config(ruta: Path) -> Config:
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe {ruta}. Copia config.example.ini como config.ini y completa los datos."
        )
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    cp.read(ruta, encoding="utf-8")

    hoja = cp.get("fuente", "hoja", fallback="0")
    return Config(
        archivo_excel=_ruta(cp.get("fuente", "archivo")),
        hoja=int(hoja) if hoja.isdigit() else hoja,
        mysql_host=cp.get("mysql", "host", fallback="localhost"),
        mysql_puerto=cp.getint("mysql", "puerto", fallback=3306),
        mysql_usuario=cp.get("mysql", "usuario"),
        # La variable de entorno tiene prioridad para no dejar la contraseña en el archivo.
        mysql_password=os.environ.get("MYSQL_PASSWORD") or cp.get("mysql", "password", fallback=""),
        mysql_base_datos=cp.get("mysql", "base_datos"),
        max_pacas_por_hora=cp.getfloat("reglas", "max_pacas_por_hora", fallback=50),
        carpeta_logs=_ruta(cp.get("ejecucion", "carpeta_logs", fallback="logs")),
        carpeta_salida=_ruta(cp.get("ejecucion", "carpeta_salida", fallback="salida")),
    )

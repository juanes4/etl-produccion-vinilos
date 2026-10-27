"""Genera la muestra pública del repo a partir del Excel real.

Reemplaza el nombre de cada operario por "Operario NN" (mismo nombre -> mismo código,
en orden de aparición). Lo demás queda igual, así el ETL da los mismos resultados.

Uso (desde la raíz del repo):
    .venv\\Scripts\\python.exe scripts\\anonimizar_datos.py
"""

from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "data" / "raw" / "data_base_transformado.xlsx"
DESTINO = RAIZ / "data" / "sample" / "produccion_vinilos_anonimizado.xlsx"

# Valores que no son personas y se conservan tal cual.
NO_PERSONAS = {"no", "n/a", "na", "no aplica"}


def anonimizar(operarios: pd.Series) -> pd.Series:
    limpios = operarios.astype("string").str.split().str.join(" ")
    nombres = [n for n in limpios.dropna().unique() if n and n.lower() not in NO_PERSONAS]
    codigos = {n: f"Operario {i:02d}" for i, n in enumerate(nombres, start=1)}
    return limpios.map(lambda n: codigos.get(n, n) if pd.notna(n) else n).astype(object)


def main() -> None:
    df = pd.read_excel(ORIGEN)
    df["Operario"] = anonimizar(df["Operario"])
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(DESTINO, index=False)
    print(f"{len(df)} filas -> {DESTINO.relative_to(RAIZ)}")
    print(df["Operario"].value_counts(dropna=False).head(10).to_string())


if __name__ == "__main__":
    main()

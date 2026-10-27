"""Catálogos de negocio usados en la limpieza.

Fuente: hoja "TABLA CODIGOS" del archivo SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm.
"""

# código -> (descripción, área de impacto, es paro programado)
PAROS = {
    1: ("Falla del sistema electromecánico y/o de control", "Mantenimiento", False),
    2: ("Espera de soporte de mantenimiento", "Mantenimiento", False),
    3: ("Novedad en los sistemas de potencia (aire, energía, vapor)", "Mantenimiento", False),
    4: ("Mantenimiento preventivo", "Mantenimiento", True),
    5: ("Ajuste operativo", "Producción", False),
    6: ("Limpieza por derrame operativo", "Producción", False),
    7: ("Alistamiento de máquina / Cambio de referencia", "Producción", False),
    8: ("Capacitación / Reunión", "Producción", False),
    9: ("Falta de operario", "Producción", False),
    10: ("Paro por ventaja/evacuación", "Producción", False),
    11: ("Reproceso", "Producción", False),
    12: ("Materia prima defectuosa", "Calidad", False),
    13: ("En espera por el aval del laboratorio de microbiología", "Calidad", False),
    14: ("Falta de materia prima", "Almacén de materias primas", False),
    15: ("Cambio de insumos (roscadores, O'ring, etiquetas)", "Paro programado", True),
    16: ("Alimentación y aseo de la zona de trabajo y la máquina", "Paro programado", True),
    17: ("Pausa activa", "Paro programado", True),
    # El código 18 no aparece en TABLA CODIGOS; se clasifica como paro programado.
    18: ("Desinfección", "Paro programado", True),
}

# Correcciones de errores de digitación en el nombre de la línea de producto.
CORRECCIONES_LINEA = {
    "Alocdor": "Alocolor",
    "Stilo Kids": "Estilo Kids",
}

# Valores de Operario que en realidad significan "no aplica".
OPERARIO_NO_APLICA = {"no", "n/a", "na", "no aplica"}

SIN_REGISTRO = "Sin registro"
NO_APLICA = "No aplica"

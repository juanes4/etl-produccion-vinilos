"""Ejecutar con:  .venv\\Scripts\\python.exe -m unittest discover -s tests"""

import unittest

import pandas as pd

from etl.transformar import (
    describir_producto,
    describir_turno,
    normalizar_referencia,
    transformar,
)


def fila(fecha, maquina, pacas, horas, tipo, horas_paro, turno="6am-2pm (Turno 1)", operario="Operario 01"):
    return {
        "Fecha": fecha, "Maquina": maquina, "Operario": operario, "Referencia": "Torre 22cc (6 col)",
        "Pacas producidas": pacas, "Horas trabajadas": horas, "Turno": turno,
        "Tipo de Paro": tipo, "Horas Paro": horas_paro,
    }


class TestNormalizacion(unittest.TestCase):
    def test_referencias(self):
        self.assertEqual(normalizar_referencia("Tris 15cc (6col)"), "Tris 15cc (6 col)")
        self.assertEqual(normalizar_referencia("Parchesitos 125 cc"), "Parchesitos 125cc")
        self.assertEqual(normalizar_referencia("Alocdor 22cc (6col)"), "Alocolor 22cc (6 col)")
        self.assertEqual(normalizar_referencia("Stilo Kids 22cc (6 col)"), "Estilo Kids 22cc (6 col)")

    def test_producto(self):
        self.assertEqual(describir_producto("Torre 22cc (12 col)"), ("Torre", 22, 12))
        self.assertEqual(describir_producto("Parchesitos 125cc"), ("Parchesitos", 125, None))
        self.assertEqual(describir_producto("No aplica"), ("No aplica", None, None))

    def test_turnos(self):
        self.assertEqual(describir_turno("10pm-6am (Turno 3)"), ("22:00:00", "06:00:00", 8.0))
        self.assertEqual(describir_turno("6am-4:30pm"), ("06:00:00", "16:30:00", 10.5))
        self.assertEqual(describir_turno("No aplica"), (None, None, None))


class TestTransformar(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame([
            # Turno 1: tres paros; solo la primera fila trae pacas/horas
            fila("2024-01-02", "Vinilos_1", 60, 8, "[05] Ajuste operativo", 0.5),
            fila("2024-01-02", "Vinilos_1", 0, 0, "[16] Alimentación y aseo", 0.5),
            fila("2024-01-02", "Vinilos_1", 0, 0, "[17] Pausa activa", 0.25),
            # Turno 2: misma clave, el código vuelve a empezar -> registro nuevo
            fila("2024-01-02", "Vinilos_1", 55, 8, "[01] Falla del sistema", 1.0),
            # Turno 3: atípico (pacas/hora muy altas)
            fila("2024-01-03", "Vinilos_2", 4000, 8, "[17] Pausa activa", 0.1),
            # Turno 4: sin pacas registradas, código "No" como operario
            fila("2024-01-03", "Vinilos_3", None, None, "[14] Falta de materia prima", 2.0, operario="No"),
        ])
        self.res = transformar(self.df, max_pacas_por_hora=50)

    def test_reconstruye_turnos_sin_duplicar_pacas(self):
        r = self.res.registros
        self.assertEqual(len(r), 4)
        self.assertEqual(r["pacas"].sum(), 60 + 55 + 4000)
        self.assertEqual(len(self.res.paros), 6)

    def test_totales_de_paro(self):
        primero = self.res.registros.iloc[0]
        self.assertAlmostEqual(primero["horas_paro"], 1.25)
        self.assertAlmostEqual(primero["horas_paro_programado"], 0.75)  # códigos 16 y 17
        self.assertEqual(primero["num_paros"], 3)

    def test_banderas_y_nulos(self):
        r = self.res.registros
        self.assertTrue(r.iloc[2]["es_atipico"])
        self.assertTrue(pd.isna(r.iloc[3]["pacas"]))  # no se convierte a 0
        self.assertEqual(r.iloc[3]["operario"], "No aplica")

    def test_columnas_faltantes(self):
        with self.assertRaises(ValueError):
            transformar(self.df.drop(columns=["Horas Paro"]), 50)


if __name__ == "__main__":
    unittest.main()

# ETL de producción de máquinas de vinilos: Excel → Python (pandas) → MySQL → Grafana

Pipeline ETL en Python que toma el Excel de seguimiento de producción de una planta de témperas y vinilos, corrige sus errores de registro, lo carga como **modelo estrella en MySQL** y alimenta un **dashboard de Grafana** con indicadores de producción, disponibilidad y causas de paro. Corre a diario con el Programador de tareas de Windows.

**Stack:** Python 3 · pandas · MySQL 8 · Grafana · SQL · Windows Task Scheduler

> Proyecto final del curso *Inteligencia de Negocios*. Los nombres de los operarios se anonimizaron; el resto de los datos es real.

## El problema

La planta registraba la producción de 4 máquinas llenadoras en un Excel con macros, que se exportaba a una tabla de 16.533 filas (enero de 2022 a noviembre de 2025). Al analizarla aparecieron varios problemas:

- **Pacas contadas de más o de menos.** El archivo tiene una fila por *paro*, no por turno. La primera fila de cada turno trae las pacas y las siguientes las repiten en 0. Por eso las 16.533 filas corresponden en realidad a **6.067 turnos**, y cualquier promedio sobre las filas da un resultado incorrecto.
- **Datos digitados a mano:** la misma referencia escrita de varias formas (`125 cc`, `(6col)`, `Alocdor`), operario y turno vacíos en todo 2022, y 11 turnos con miles de pacas en 8 horas (probablemente se registraron unidades en lugar de pacas). Esos 11 turnos suman el 14 % de toda la producción.
- **Sin historial ni automatización:** el script anterior ([legacy/](legacy/)) sincronizaba fila por fila con la contraseña escrita en el código y sin transacciones.

## La solución

```
Excel ──► extraer.py ──► transformar.py ──► cargar.py ──► MySQL (modelo estrella) ──► Grafana
                               │                 │
                               │                 └─► etl_ejecuciones (bitácora de cada corrida)
                               └─► salida/*.csv  (modo simulación, sin base de datos)
```

1. **Extraer**: lee el Excel y calcula su huella SHA-256. Si el archivo no cambió desde la última carga exitosa, no recarga.
2. **Transformar**: reconstruye cada turno, normaliza los textos, valida rangos y marca los registros atípicos o inconsistentes **sin borrarlos**.
3. **Cargar**: hace *upsert* de las dimensiones (los ids no cambian) y reemplaza los hechos dentro de **una sola transacción**. Si algo falla hace rollback y Grafana sigue mostrando la última carga buena.
4. **Registrar**: cada corrida queda en `etl_ejecuciones` con su estado, duración y un reporte de calidad en JSON, también visible en el dashboard.

### Hallazgos

Con los datos limpios (se excluyen los turnos atípicos e inconsistentes):

- Disponibilidad global del **86,3 %**. Vinilos_2 es la más baja (77,8 %) y Vinilos_4 la más alta (88,8 %).
- Tres causas explican el **63 % de las horas de paro**: alimentación y aseo (23,7 %), ajuste operativo (21,5 %) y limpieza por derrame (18,3 %).
- El área de **Producción** genera más paros que Mantenimiento, Calidad y Almacén juntos.
- Las pacas por hora dependen mucho de la referencia (125 cc ≈ 30/h frente a 15 cc ≈ 5/h). Por eso el dashboard compara máquinas solo dentro de una misma referencia.

## Estructura del repositorio

```
.
├── etl/                    Paquete del pipeline (python -m etl)
│   ├── extraer.py          Lectura del Excel y huella SHA-256
│   ├── transformar.py      Limpieza, reconstrucción de turnos y banderas de calidad
│   ├── cargar.py           Esquema, upsert de dimensiones y carga transaccional
│   ├── catalogos.py        Códigos de paro 1–18 con su área responsable
│   ├── config.py           Lectura de config.ini y variables de entorno
│   └── main.py             Orquestación, logs y bitácora
├── sql/
│   ├── 00_base_datos_y_usuarios.sql   Base y usuarios (ETL y Grafana de solo lectura)
│   ├── 01_esquema.sql                 Modelo estrella + bitácora
│   └── 02_vistas.sql                  Vistas que consume Grafana
├── grafana/
│   └── dashboard_vinilos.json         Dashboard listo para importar
├── scripts/
│   ├── ejecutar_etl.bat               Ejecución manual o programada
│   ├── programar_tarea.ps1            Registra la tarea diaria en Windows
│   └── anonimizar_datos.py            Genera la muestra pública a partir del Excel real
├── tests/                  Pruebas unitarias de la transformación
├── data/
│   ├── sample/             Excel anonimizado (es el que usa config.example.ini)
│   └── raw/                Datos originales; no se versionan
├── legacy/                 Primera versión del proyecto, como referencia
├── config.example.ini
└── requirements.txt
```

## Cómo ejecutarlo

**Requisitos:** Python 3.10 o superior, MySQL 8.0.19 o superior (por la sintaxis `INSERT ... AS alias ON DUPLICATE KEY UPDATE`) y Grafana con el origen de datos MySQL que trae incluido.

### 1. Instalación

```powershell
git clone <url-del-repo>
cd etl-produccion-vinilos
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy config.example.ini config.ini
```

### 2. Probar sin base de datos

```powershell
scripts\ejecutar_etl.bat --simulacion
.venv\Scripts\python.exe -m unittest discover -s tests
```

La simulación deja las tablas limpias en `salida/` (CSV) y el reporte de calidad en `salida/calidad.json`.

### 3. Cargar a MySQL

1. Cambia las dos contraseñas de [sql/00_base_datos_y_usuarios.sql](sql/00_base_datos_y_usuarios.sql) y ejecútalo una vez como `root`. Crea la base `temperas_vinilos`, el usuario `etl_vinilos` (para el ETL) y el usuario `grafana` (solo lectura).
2. Define la contraseña del ETL en una variable de entorno para que no quede en ningún archivo:
   ```powershell
   setx MYSQL_PASSWORD "la_clave_de_etl_vinilos"   # abre una terminal nueva después
   ```
3. Ejecuta la primera carga. Las tablas y vistas se crean solas:
   ```powershell
   scripts\ejecutar_etl.bat
   ```
4. Prográmalo cada 24 horas:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\programar_tarea.ps1 -Hora "02:00"
   ```
   Si el PC está apagado a esa hora, la tarea corre al encenderlo. Si falla, se reintenta 3 veces.

| Comando | Efecto |
|---|---|
| `scripts\ejecutar_etl.bat` | Carga solo si el Excel cambió desde la última carga exitosa |
| `scripts\ejecutar_etl.bat --forzar` | Recarga aunque el Excel no haya cambiado |
| `scripts\ejecutar_etl.bat --simulacion` | Solo extrae y limpia; no se conecta a MySQL |
| `.venv\Scripts\python.exe -m etl --config otra.ini` | Usa otro archivo de configuración |

Los logs quedan en `logs/etl.log` (con rotación).

### 4. Dashboard en Grafana

1. Instala [Grafana OSS](https://grafana.com/grafana/download?platform=windows) y entra a http://localhost:3000 (usuario y clave inicial: `admin`/`admin`).
2. En *Connections → Data sources → Add → MySQL* configura: host `localhost:3306`, base `temperas_vinilos`, usuario `grafana`.
3. En *Dashboards → New → Import* sube [grafana/dashboard_vinilos.json](grafana/dashboard_vinilos.json) y elige ese origen de datos.

El dashboard tiene filtros de rango de fechas, máquina y agrupación (1, 7 o 30 días), y muestra:

- Indicadores de pacas, disponibilidad, horas de paro no programado por turno y turnos excluidos por calidad.
- Tendencia de pacas y disponibilidad por máquina.
- Pareto de causas de paro y horas de paro por área responsable.
- Tendencia de las 3 causas principales, normalizada por número de turnos.
- Productividad por referencia y comparación entre máquinas para una misma referencia.
- Bitácora de las últimas ejecuciones del ETL.

## Modelo de datos

```
dim_fecha ───┐
dim_maquina ─┤
dim_operario ┼──► fact_produccion (1 fila por turno) ◄── fact_paro (1 fila por turno × código de paro) ──► dim_paro
dim_producto ┤
dim_turno ───┘
```

Grafana consulta tres vistas: `vw_produccion`, `vw_paros` y `vw_kpi_diario_maquina`.

**Cómo se reconstruyen los turnos.** Una fila es continuación del turno anterior si cumple cuatro condiciones: tiene la misma fecha, máquina, operario, referencia y turno; su código de paro es mayor que el de la fila anterior; y trae pacas = 0 y horas = 0. El total de pacas y de horas se conserva exactamente.

**Disponibilidad** = (horas trabajadas − horas de paro) / (horas trabajadas − paros programados). Las horas de paro ya están incluidas en las horas trabajadas. Se consideran paros programados los códigos 4, 15, 16, 17 y 18 (mantenimiento preventivo, cambio de insumos, aseo, pausas activas y desinfección).

## Reglas de limpieza

| Problema encontrado | Tratamiento |
|---|---|
| Una referencia escrita de varias formas: `(6col)`, `125 cc`, `Alocdor`, `Stilo Kids` | Se normaliza (1.521 filas). De la referencia se extraen la línea, los cc y el número de colores |
| Operario o turno vacío (todo 2022 y el 61 % de 2023) | Se reemplaza por `Sin registro`; el operario `No` pasa a `No aplica` |
| Pacas vacías | Se dejan en NULL, no en 0, para no sesgar los promedios |
| 11 turnos de Vinilos_1 (julio de 2023) con 3.500–9.400 pacas en 8 h | Se marcan con `es_atipico` (más de 50 pacas/hora) y quedan fuera de los KPI |
| 3 turnos con más horas de paro que horas trabajadas | Se marcan con `es_inconsistente` y quedan fuera de los KPI |
| Valores negativos, de más de 24 h o códigos de paro desconocidos | Se anulan y se cuentan en el reporte de calidad |

## Decisiones técnicas

- **Marcar en lugar de borrar.** Los registros dudosos se cargan con una bandera y las vistas los excluyen. Así se pueden auditar desde la base de datos.
- **Carga idempotente.** Ejecutar el ETL dos veces con el mismo archivo da el mismo resultado, y si el Excel no cambió ni siquiera se recarga.
- **Credenciales fuera del código.** La contraseña se lee de `MYSQL_PASSWORD`, `config.ini` no se versiona y Grafana usa un usuario de solo lectura.
- **Configuración en un solo lugar.** El umbral de atípicos, las rutas y la conexión están en `config.ini`; no hay valores fijos en el código.

## Limitaciones conocidas

- El Excel de entrada solo contiene turnos que tuvieron al menos un paro, porque así lo generaba el script original ([legacy/limpieza.py](legacy/limpieza.py)). Frente a la base original faltan unas 3.800 pacas (≈1 %), así que la disponibilidad real es un poco más alta que la calculada.
- El código 18 (Desinfección) no aparece en la tabla de códigos de la empresa; se clasificó como paro programado.
- La tarea programada y los scripts `.bat`/`.ps1` son para Windows. En Linux o macOS basta con `python -m etl` y un cron.

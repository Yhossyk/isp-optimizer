# ISP OPTIMIZER

Aplicación web académica del **Método de Gradientes Conjugados Precondicionado (GCP)** aplicado al análisis financiero de la expansión de infraestructura de red de un ISP ficticio (*Conecta Bolivia*).
UMSA · Ingeniería de Sistemas · Métodos Numéricos. Basado en Suñagua (2020), *Método de Gradientes Conjugados Precondicionado*, Rev. Boliviana de Matemática–UMSA, 04, 2–7.

> Todos los datos (matrices, vectores, montos en miles de Bs) son **supuestos académicos**, no cotizaciones ni estadísticas reales.
> `A·x = b` es un modelo lineal de necesidades de inversión; **no** es por sí solo una optimización restringida por presupuesto.

## Módulos (10)
1 Inicio · 2 Caso de estudio · 3 Modelo matemático (SPD: valores propios + Sylvester) · 4 Editor de datos (modo manual / escenarios) ·
5 Tres escenarios · 6 Solución directa (Cholesky) · 7 GC vs GCP (tablas por iteración y gráfico de residuos) ·
8 Errores (Ea, Er, Ep) y condicionamiento (κ(A), κ(M^-1/2·A·M^-1/2)) · 9 Pruebas QA ejecutables · 10 Conclusiones **dinámicas**, recomendaciones y bibliografía.

## Arquitectura
```
isp_optimizer/
├── app.py                 # Flask: rutas HTTP (sin lógica matemática)
├── backend/
│   ├── numerics.py        # Cholesky, GC, GCP-Jacobi, SPD, κ, errores
│   ├── validation.py      # dimensiones, finitud, simetría/SPD, tol, max_iter, Jacobi
│   ├── scenarios.py       # 3 escenarios (copias independientes) + variables
│   ├── analysis.py        # orquesta todo y arma la respuesta JSON (con firma de datos)
│   ├── conclusions.py     # conclusiones y recomendaciones generadas desde los resultados
│   ├── qa.py              # pruebas de calidad que ejecutan código real
│   └── database.py        # SQLite: historial y escenarios guardados
├── templates/index.html   # los 10 módulos
├── static/{css,js,vendor} # estilos, lógica de interfaz, Chart.js (local)
├── tests/test_numerics.py # pruebas unitarias
├── instance/              # aquí se crea isp_optimizer.db
├── requirements.txt · Procfile · README.md
```
**Fuente única de datos:** el objeto `S` del frontend. Cada edición marca los resultados como *desactualizados* y recalcula (con descarte de respuestas obsoletas). Cada resultado lleva una **firma** (hash de A, b, x0, tol, max_iter, precond) para no mezclar versiones.

## Instalación y ejecución local
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                                          # http://127.0.0.1:5000
```
Nombre del estudiante/docente (Módulo 1), opcional:
```bash
STUDENT_NAME="Tu Nombre" TEACHER_NAME="Nombre Docente" python app.py
```
## Base de datos (SQLite)
Se crea sola al iniciar en `instance/isp_optimizer.db` (otra ruta: variable `ISP_DB_PATH`).
- `simulations`: historial (fecha, datos A/b/x0, parámetros, soluciones, iteraciones, residuos, κ). Se guarda con **«Ejecutar y guardar en historial»**.
- `saved_scenarios`: escenarios propios con nombre.
La BD solo **registra**; al cargar un registro se **recalcula**, nunca se reutilizan resultados almacenados.

## Pruebas
```bash
python -m unittest discover -s tests -v    # unitarias (backend)
```
y en la web, Módulo 9 → «Ejecutar todas las pruebas» (11 pruebas; la nº 10 verifica en el navegador que gráficos, tablas y conclusiones coinciden con el último cálculo).

## Despliegue
`Procfile` listo para plataformas tipo Render/Railway/Heroku (`gunicorn app:app`). En hosting con disco efímero el historial SQLite puede borrarse al reiniciar.
**Este repositorio aún no está publicado ni la página desplegada**: debes subirlo a GitHub/GitLab (público) y desplegarlo tú para obtener los dos enlaces del desafío.

## Auditoría matemática (resumen)
| Escenario | SPD | κ(A) | κ precond. (Jacobi) | GC / GCP (it.) |
|---|---|---|---|---|
| Ideal | sí (λ 0.903…1.550) | 1.717 | 1.717 | 4 / 4 |
| Estrés (1.15·A₁) | sí (λ 1.038…1.782) | 1.717 | 1.717 | 4 / 4 |
| Mal condicionado | sí (λ 0.976…1.0·10⁶) | 1.025·10⁶ | 1.499 | 5 / 4 |

Los tres sistemas cumplen `A·x_esperado = b` (error ≤ 1.4·10⁻¹⁴); no hubo que corregir datos. En los escenarios 1 y 2 Jacobi **no aporta** mejora (diagonal casi uniforme); en el 3 reduce κ en ≈ 6.8·10⁵. Con n = 4 el GC termina en ≤ 4 pasos en aritmética exacta, así que la diferencia de 1 iteración en el escenario 3 es efecto de redondeo.

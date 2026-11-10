"""Gestión de escenarios predeterminados (los tres comparten las mismas 4 variables)."""
from __future__ import annotations

import copy

VARIABLES = [
    {"id": "X1", "name": "Fibra óptica y ampliación de cobertura", "short": "Fibra óptica", "unit": "Miles de Bs"},
    {"id": "X2", "name": "Routers y switches", "short": "Routers y switches", "unit": "Miles de Bs"},
    {"id": "X3", "name": "Servidores y equipos de distribución", "short": "Servidores", "unit": "Miles de Bs"},
    {"id": "X4", "name": "Mantenimiento y soporte técnico", "short": "Mantenimiento", "unit": "Miles de Bs"},
]

_A1 = [
    [1.21, 0.20, 0.01, 0.0],
    [0.20, 1.22, 0.20, 0.01],
    [0.01, 0.20, 1.22, 0.20],
    [0.0, 0.01, 0.20, 1.21],
]

_SCENARIOS = {
    "ideal": {
        "id": "ideal",
        "name": "Escenario 1 · Ideal",
        "short": "Ideal",
        "color": "#22d3ee",
        "description": (
            "Situación financiera estable: costos controlados y planificación adecuada. "
            "Las cuatro áreas pesan de forma parecida y el acoplamiento entre ellas es débil."
        ),
        "justification": (
            "La diagonal (≈1.21–1.22) es dominante: cada área depende sobre todo de su propia "
            "inversión. Los acoplamientos 0.20 entre áreas contiguas (fibra↔routers, routers↔servidores, "
            "servidores↔mantenimiento) modelan que una ampliación de una área exige inversión en la vecina; "
            "los de 0.01 modelan dependencias remotas casi despreciables. La matriz es simétrica porque se "
            "supone que la dependencia es recíproca. Todos los coeficientes son supuestos académicos."
        ),
        "A": _A1,
        "b": [66.70, 50.70, 32.90, 16.40],
        "expected": [50.0, 30.0, 20.0, 10.0],
    },
    "stress": {
        "id": "stress",
        "name": "Escenario 2 · Estrés financiero",
        "short": "Estrés",
        "color": "#f59e0b",
        "description": (
            "Incremento de costos de infraestructura, equipos y mantenimiento, con mayores "
            "requerimientos de inversión en las cuatro áreas."
        ),
        "justification": (
            "A₂ = 1.15·A₁ representa un aumento uniforme del 15 % en los costos asociados a cada área y a "
            "sus acoplamientos; b₂ recoge los nuevos requerimientos. Es una simplificación académica: no es "
            "una inflación diferenciada por componente. Como A₂ es un múltiplo escalar de A₁, κ(A₂)=κ(A₁): "
            "el estrés desplaza el punto de equilibrio x pero no empeora el condicionamiento."
        ),
        "A": [[round(1.15 * v, 12) for v in row] for row in _A1],
        "b": [99.5095, 74.865, 51.9915, 26.358],
        "expected": [65.0, 38.0, 28.0, 14.0],
    },
    "ill": {
        "id": "ill",
        "name": "Escenario 3 · Mal condicionado",
        "short": "Mal condicionado",
        "color": "#a78bfa",
        "description": (
            "Variables con escalas muy distintas y relaciones fuertes entre componentes: "
            "los coeficientes van de 1 a 10⁶."
        ),
        "justification": (
            "Se supone que las áreas se miden con escalas muy diferentes (p. ej. mantenimiento por "
            "unidades de servicio con coeficiente 10⁶ frente a fibra con coeficiente 1) y que servidores y "
            "mantenimiento están fuertemente acoplados (10 000). El mal condicionamiento proviene sobre todo "
            "del mal escalamiento diagonal, por lo que el precondicionador de Jacobi es el adecuado."
        ),
        "A": [
            [1.0, 1.5, 5.0, 0.0],
            [1.5, 100.0, 120.0, 400.0],
            [5.0, 120.0, 10000.0, 10000.0],
            [0.0, 400.0, 10000.0, 1000000.0],
        ],
        "b": [330.0, 17320.0, 556400.0, 20370000.0],
        "expected": [80.0, 50.0, 35.0, 20.0],
    },
}

ORDER = ["ideal", "stress", "ill"]


def get_scenario(sid: str) -> dict | None:
    """Devuelve una COPIA independiente (modificarla no altera el escenario original)."""
    s = _SCENARIOS.get(sid)
    return copy.deepcopy(s) if s else None


def all_scenarios() -> list[dict]:
    return [get_scenario(s) for s in ORDER]


def is_unmodified(sid: str | None, A, b) -> bool:
    s = _SCENARIOS.get(sid) if sid else None
    if not s:
        return False
    return all(abs(a - c) <= 1e-12 for ra, rc in zip(A, s["A"]) for a, c in zip(ra, rc)) and all(
        abs(a - c) <= 1e-12 for a, c in zip(b, s["b"])
    )

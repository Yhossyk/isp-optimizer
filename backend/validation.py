"""Validación de entradas antes de ejecutar cualquier método numérico."""
from __future__ import annotations

import math

import numpy as np

N = 4
PRECONDITIONERS = ("jacobi", "none")
DEFAULTS = {"tol": 1e-6, "max_iter": 1000, "precond": "jacobi"}


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str):
        try:
            f = float(v.replace(",", "."))
            return f if math.isfinite(f) else None
        except ValueError:
            return None
    return None


def parse_inputs(payload: dict):
    """Devuelve (inputs, errores). `inputs` es None si hay errores.

    Cada error es {"code", "message"} con texto comprensible para el usuario.
    """
    errors = []
    if not isinstance(payload, dict):
        return None, [{"code": "bad_payload", "message": "La solicitud no contiene datos válidos."}]

    A_raw, b_raw = payload.get("A"), payload.get("b")
    A = b = None
    if not (isinstance(A_raw, list) and len(A_raw) == N and all(isinstance(r, list) and len(r) == N for r in A_raw)):
        errors.append({"code": "dim_A", "message": f"A debe ser una matriz de {N}×{N}."})
    else:
        vals = [[_num(v) for v in r] for r in A_raw]
        bad = [f"A[{i + 1}][{j + 1}]" for i, r in enumerate(vals) for j, v in enumerate(r) if v is None]
        if bad:
            errors.append({"code": "nan_A", "message": "Hay valores no numéricos o vacíos en: " + ", ".join(bad[:6]) + ("…" if len(bad) > 6 else "") + "."})
        else:
            A = np.array(vals, dtype=float)

    if not (isinstance(b_raw, list) and len(b_raw) == N):
        errors.append({"code": "dim_b", "message": f"b debe tener {N} elementos."})
    else:
        vals = [_num(v) for v in b_raw]
        bad = [f"b[{i + 1}]" for i, v in enumerate(vals) if v is None]
        if bad:
            errors.append({"code": "nan_b", "message": "Hay valores no numéricos o vacíos en: " + ", ".join(bad) + "."})
        else:
            b = np.array(vals, dtype=float)
            if np.linalg.norm(b) == 0.0:
                errors.append({"code": "b_zero", "message": "b no puede ser el vector nulo: el residuo relativo ||r||/||b|| no está definido."})

    x0_raw = payload.get("x0")
    x0 = np.zeros(N)
    if x0_raw is not None:
        if not (isinstance(x0_raw, list) and len(x0_raw) == N):
            errors.append({"code": "dim_x0", "message": f"x0 debe tener {N} elementos."})
        else:
            vals = [_num(v) for v in x0_raw]
            if any(v is None for v in vals):
                errors.append({"code": "nan_x0", "message": "x0 contiene valores no numéricos o vacíos."})
            else:
                x0 = np.array(vals, dtype=float)

    tol = _num(payload.get("tol", DEFAULTS["tol"]))
    if tol is None or not (0.0 < tol < 1.0):
        errors.append({"code": "tol", "message": "La tolerancia debe ser un número entre 0 y 1 (p. ej. 1e-6)."})
    mi_raw = payload.get("max_iter", DEFAULTS["max_iter"])
    mi = _num(mi_raw)
    if mi is None or mi != int(mi) or not (1 <= mi <= 10000):
        errors.append({"code": "max_iter", "message": "El máximo de iteraciones debe ser un entero entre 1 y 10000."})
    precond = payload.get("precond", DEFAULTS["precond"])
    if precond not in PRECONDITIONERS:
        errors.append({"code": "precond", "message": "Precondicionador no reconocido (use 'jacobi' o 'none')."})

    if errors:
        return None, errors
    return {"A": A, "b": b, "x0": x0, "tol": tol, "max_iter": int(mi), "precond": precond}, []


def structural_errors(spd: dict, precond: str, A: np.ndarray) -> list:
    """Errores que impiden ejecutar GC/GCP según el diagnóstico de la matriz."""
    errs = []
    if not spd["symmetric"]:
        pairs = ", ".join(f"(a{p['i']}{p['j']}={p['aij']:.6g} ≠ a{p['j']}{p['i']}={p['aji']:.6g})" for p in spd["asymmetric_pairs"][:3])
        errs.append({"code": "not_symmetric", "message": f"A no es simétrica (A ≠ Aᵀ). Diferencia máxima {spd['max_asymmetry']:.3g}. {pairs}"})
    elif not spd["spd"]:
        why = []
        if not spd.get("eig_positive"):
            why.append(f"el menor valor propio es {spd['min_eig']:.6g} (≤ 0)")
        if not spd.get("minors_positive"):
            bad = [m["k"] for m in spd["minors"] if not m["positive"]]
            why.append("los menores principales de orden " + ", ".join(map(str, bad)) + " no son positivos")
        errs.append({"code": "not_spd", "message": "A es simétrica pero no es definida positiva: " + "; ".join(why) + ". GC y GCP no están garantizados."})
    if precond == "jacobi" and np.any(np.diag(A) <= 0):
        errs.append({"code": "jacobi_diag", "message": "Jacobi requiere que todos los elementos de la diagonal de A sean positivos."})
    return errs

"""Orquestación: valida, resuelve (Cholesky, GC, GCP), calcula errores y redacta conclusiones."""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np

from . import conclusions, numerics, scenarios, validation


def sanitize(o):
    """Convierte ndarray/NumPy a tipos JSON y NaN/inf a None."""
    if isinstance(o, dict):
        return {k: sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [sanitize(v) for v in o]
    if isinstance(o, np.ndarray):
        return sanitize(o.tolist())
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if math.isfinite(v) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def signature(inp: dict) -> str:
    """Huella de la versión concreta de (A, b, x0, tol, max_iter, precond)."""
    raw = json.dumps(
        {"A": inp["A"].tolist(), "b": inp["b"].tolist(), "x0": inp["x0"].tolist(),
         "tol": inp["tol"], "mi": inp["max_iter"], "p": inp["precond"]},
        sort_keys=True,
    )
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _ideal_total():
    s = scenarios.get_scenario("ideal")
    import numpy as _np

    return float(_np.sum(numerics.cholesky_solve(_np.array(s["A"]), _np.array(s["b"]))["x"]))


def analyze(payload: dict) -> dict:
    """Análisis completo. Nunca lanza excepciones por datos del usuario."""
    scenario_id = payload.get("scenario_id") if isinstance(payload, dict) else None
    inp, errs = validation.parse_inputs(payload)
    if errs:
        res = {"valid": False, "stage": "parse", "errors": errs, "inputs": None, "signature": None}
        res["conclusions"] = conclusions.build(res, {"label": "Datos no válidos"})
        return sanitize(res)

    A, b = inp["A"], inp["b"]
    sc = scenarios.get_scenario(scenario_id) if scenario_id else None
    unmodified = scenarios.is_unmodified(scenario_id, A.tolist(), b.tolist())
    if sc and unmodified:
        label = sc["name"]
    elif sc:
        label = f"Escenario personalizado (basado en {sc['short']})"
    else:
        label = "Modo manual"

    spd = numerics.spd_report(A)
    s_errs = validation.structural_errors(spd, inp["precond"], A)
    inputs_echo = {
        "A": A.tolist(), "b": b.tolist(), "x0": inp["x0"].tolist(),
        "tol": inp["tol"], "max_iter": inp["max_iter"], "precond": inp["precond"],
    }
    base = {"scenario_id": scenario_id, "unmodified": unmodified, "label": label,
            "inputs": inputs_echo, "signature": signature(inp), "spd": spd}
    if s_errs:
        res = {"valid": False, "stage": "structure", "errors": s_errs, **base}
        res["conclusions"] = conclusions.build(res, {"label": label})
        return sanitize(res)

    chol = numerics.cholesky_solve(A, b)
    x_ref = chol["x"]
    gc = numerics.conjugate_gradient(A, b, inp["x0"], inp["tol"], inp["max_iter"], "none")
    gcp = numerics.conjugate_gradient(A, b, inp["x0"], inp["tol"], inp["max_iter"], inp["precond"])
    cond = numerics.condition_numbers(A, inp["precond"])

    expected = None
    if sc and unmodified:
        expected = {
            "x": sc["expected"],
            "max_diff_direct": float(np.max(np.abs(np.array(sc["expected"]) - x_ref))),
            "errors_direct": numerics.error_table(x_ref, sc["expected"]),
        }

    warnings = []
    if not gc["converged"]:
        warnings.append("GC no convergió: " + gc["reason"])
    if not gcp["converged"]:
        warnings.append("GCP no convergió: " + gcp["reason"])

    res = {
        "valid": True, "stage": "ok", "errors": [], "warnings": warnings, **base,
        "cholesky": chol, "gc": gc, "gcp": gcp, "cond": cond,
        "errors_gc": numerics.error_table(gc["x"], x_ref),
        "errors_gcp": numerics.error_table(gcp["x"], x_ref),
        "expected": expected,
        "variables": scenarios.VARIABLES,
    }
    ctx = {"label": label, "scenario_id": scenario_id, "unmodified": unmodified, "baseline_total": _ideal_total()}
    res["conclusions"] = conclusions.build(res, ctx)
    return sanitize(res)


def compare_scenarios(params: dict) -> list:
    """Ejecuta los tres escenarios ORIGINALES con los parámetros dados (sin mezclar datos)."""
    out = []
    for sc in scenarios.all_scenarios():
        payload = {"A": sc["A"], "b": sc["b"], "x0": [0, 0, 0, 0], "scenario_id": sc["id"],
                   "tol": params.get("tol", validation.DEFAULTS["tol"]),
                   "max_iter": params.get("max_iter", validation.DEFAULTS["max_iter"]),
                   "precond": params.get("precond", validation.DEFAULTS["precond"])}
        r = analyze(payload)
        entry = {"id": sc["id"], "name": sc["name"], "short": sc["short"], "color": sc["color"], "valid": r["valid"],
                 "A": sc["A"], "b": sc["b"], "expected": sc["expected"]}
        if r["valid"]:
            x_ref = r["cholesky"]["x"]
            entry.update(
                x_ref=x_ref, x_gc=r["gc"]["x"], x_gcp=r["gcp"]["x"],
                errors_gcp=r["errors_gcp"], errors_gc=r["errors_gc"],
                it_gc=r["gc"]["iterations"], it_gcp=r["gcp"]["iterations"],
                kappa_A=r["cond"]["kappa_A"], kappa_M=r["cond"]["kappa_M"],
                rel_gcp=r["gcp"]["final_rel_residual"], rel_gc=r["gc"]["final_rel_residual"],
                conv_gc=r["gc"]["converged"], conv_gcp=r["gcp"]["converged"],
                brief=conclusions.financial_brief(x_ref),
                total=float(sum(x_ref)),
            )
        else:
            entry["errors"] = r["errors"]
        out.append(entry)
    return sanitize(out)


def scenario_properties() -> list:
    """Propiedades matemáticas (simetría, SPD, valores propios, menores, κ) de los tres escenarios."""
    out = []
    for sc in scenarios.all_scenarios():
        A = np.array(sc["A"])
        spd = numerics.spd_report(A)
        out.append(sanitize({
            "id": sc["id"], "name": sc["name"], "spd": spd,
            "cond": numerics.condition_numbers(A, "jacobi"),
        }))
    return out

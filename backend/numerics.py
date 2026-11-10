"""Núcleo numérico de ISP OPTIMIZER.

Contiene únicamente lógica matemática (sin Flask ni SQLite):
  - Factorización de Cholesky y sustituciones (solución directa de referencia).
  - Gradientes Conjugados (GC) y Gradientes Conjugados Precondicionados (GCP, Jacobi).
  - Diagnósticos: simetría, definición positiva, valores propios, menores principales,
    números de condición y errores por componente.
"""
from __future__ import annotations

import numpy as np


class NotPositiveDefiniteError(ValueError):
    """La factorización de Cholesky encontró un pivote no positivo."""

    def __init__(self, index: int, value: float):
        super().__init__(f"Pivote no positivo en la fila {index} (valor {value:.6g}).")
        self.index = index
        self.value = value


# ---------------------------------------------------------------------------
# Solución directa: Cholesky
# ---------------------------------------------------------------------------
def cholesky_decomposition(A: np.ndarray) -> np.ndarray:
    """Devuelve L triangular inferior con A = L·Lᵀ (A simétrica definida positiva)."""
    n = A.shape[0]
    L = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1):
            s = A[i, j] - np.dot(L[i, :j], L[j, :j])
            if i == j:
                if not np.isfinite(s) or s <= 0.0:
                    raise NotPositiveDefiniteError(i + 1, float(s))
                L[i, i] = np.sqrt(s)
            else:
                L[i, j] = s / L[j, j]
    return L


def forward_substitution(L: np.ndarray, b: np.ndarray):
    """Resuelve L·y = b. Devuelve (y, pasos de texto)."""
    n = len(b)
    y = np.zeros(n)
    steps = []
    for i in range(n):
        s = float(np.dot(L[i, :i], y[:i]))
        y[i] = (b[i] - s) / L[i, i]
        steps.append(
            f"y{i + 1} = (b{i + 1} − Σ L{i + 1}j·yj) / L{i + 1}{i + 1} "
            f"= ({b[i]:.6g} − {s:.6g}) / {L[i, i]:.6g} = {y[i]:.8g}"
        )
    return y, steps


def backward_substitution(U: np.ndarray, y: np.ndarray):
    """Resuelve U·x = y con U triangular superior. Devuelve (x, pasos de texto)."""
    n = len(y)
    x = np.zeros(n)
    steps = []
    for i in range(n - 1, -1, -1):
        s = float(np.dot(U[i, i + 1:], x[i + 1:]))
        x[i] = (y[i] - s) / U[i, i]
        steps.append(
            f"x{i + 1} = (y{i + 1} − Σ Lᵀ{i + 1}j·xj) / Lᵀ{i + 1}{i + 1} "
            f"= ({y[i]:.8g} − {s:.8g}) / {U[i, i]:.6g} = {x[i]:.8g}"
        )
    return x, steps


def cholesky_solve(A: np.ndarray, b: np.ndarray) -> dict:
    L = cholesky_decomposition(A)
    Lt = L.T.copy()
    y, f_steps = forward_substitution(L, b)
    x, b_steps = backward_substitution(Lt, y)
    nb = np.linalg.norm(b)
    return {
        "L": L,
        "Lt": Lt,
        "y": y,
        "x": x,
        "forward_steps": f_steps,
        "backward_steps": b_steps[::-1],  # se muestran en orden x1..xn
        "check_abs": float(np.linalg.norm(b - A @ x)),
        "check_rel": float(np.linalg.norm(b - A @ x) / nb) if nb > 0 else None,
        "factor_check": float(np.max(np.abs(L @ Lt - A))),
    }


# ---------------------------------------------------------------------------
# Gradientes Conjugados (con o sin precondicionador)
# ---------------------------------------------------------------------------
def conjugate_gradient(A, b, x0, tol=1e-6, max_iter=1000, precond="none") -> dict:
    """Gradientes Conjugados.

    precond = "none"   → GC clásico (M = I).
    precond = "jacobi" → GCP con M = diag(A); se resuelve M·z = r dividiendo por diag(A).

    Criterio de parada: ||b − A·xk||₂ / ||b||₂ < tol, usando el residuo REAL
    (recalculado como b − A·xk) en cada iteración y al finalizar.
    """
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float)
    n = len(b)
    nb = float(np.linalg.norm(b))
    if nb == 0.0:
        raise ValueError("||b|| = 0: el residuo relativo no está definido.")

    if precond == "jacobi":
        d = np.diag(A)
        if np.any(d <= 0) or not np.all(np.isfinite(d)):
            raise ValueError("Jacobi requiere diag(A) positiva y finita.")
        minv = 1.0 / d
    else:
        minv = np.ones(n)

    x = np.array(x0, dtype=float).copy()
    r = b - A @ x
    z = minv * r  # Mz = r
    p = z.copy()
    rz = float(r @ z)

    rel = float(np.linalg.norm(r) / nb)
    rows = [_row(0, x, np.linalg.norm(r), rel, None, None, tol)]
    k = 0
    breakdown = None
    while k < max_iter and rel >= tol:
        Ap = A @ p
        pAp = float(p @ Ap)
        if not np.isfinite(pAp) or pAp <= 0.0:
            breakdown = "pᵀ·A·p ≤ 0 o no finito: la matriz no se comporta como definida positiva."
            break
        if rz == 0.0 or not np.isfinite(rz):
            breakdown = "rᵀ·z = 0 sin haber alcanzado la tolerancia."
            break
        alpha = rz / pAp
        x = x + alpha * p
        r = r - alpha * Ap
        k += 1
        z = minv * r
        rz_new = float(r @ z)
        true_r = b - A @ x
        rel = float(np.linalg.norm(true_r) / nb)
        if not (np.all(np.isfinite(x)) and np.isfinite(rel)):
            breakdown = "Se obtuvieron valores no finitos."
            break
        beta = rz_new / rz
        rows.append(_row(k, x, np.linalg.norm(true_r), rel, alpha, beta, tol))
        if rel < tol:
            break
        p = z + beta * p
        rz = rz_new

    final_r = b - A @ x
    final_rel = float(np.linalg.norm(final_r) / nb)
    finite = bool(np.all(np.isfinite(x)) and np.isfinite(final_rel))
    converged = bool(finite and final_rel < tol)
    if converged:
        reason = "Convergió: residuo relativo menor que la tolerancia."
    elif breakdown:
        reason = breakdown
    else:
        reason = "Se alcanzó el máximo de iteraciones sin cumplir la tolerancia."
    return {
        "method": "GCP-Jacobi" if precond == "jacobi" else "GC",
        "precond": precond,
        "x": x,
        "iterations": k,
        "converged": converged,
        "final_residual": float(np.linalg.norm(final_r)),
        "final_rel_residual": final_rel,
        "reason": reason,
        "rows": rows,
    }


def _row(k, x, res, rel, alpha, beta, tol):
    if k == 0:
        status = "inicial" if rel >= tol else "convergió"
    else:
        status = "convergió" if rel < tol else "continúa"
    return {
        "k": k,
        "x": [float(v) for v in x],
        "residual": float(res),
        "rel_residual": float(rel),
        "alpha": None if alpha is None else float(alpha),
        "beta": None if beta is None else float(beta),
        "status": status,
    }


# ---------------------------------------------------------------------------
# Diagnósticos de la matriz
# ---------------------------------------------------------------------------
def symmetry_report(A: np.ndarray) -> dict:
    scale = max(1.0, float(np.max(np.abs(A))))
    diff = np.abs(A - A.T)
    max_asym = float(np.max(diff))
    asym = [
        {"i": i + 1, "j": j + 1, "aij": float(A[i, j]), "aji": float(A[j, i])}
        for i in range(A.shape[0])
        for j in range(i + 1, A.shape[0])
        if diff[i, j] > 1e-10 * scale
    ]
    return {"symmetric": max_asym <= 1e-10 * scale, "max_asymmetry": max_asym, "asymmetric_pairs": asym}


def spd_report(A: np.ndarray) -> dict:
    """Simetría, valores propios, menores principales (Sylvester) y Cholesky."""
    n = A.shape[0]
    sym = symmetry_report(A)
    rep = {"square": True, **sym, "eigenvalues": None, "minors": None,
           "min_eig": None, "max_eig": None, "cholesky_ok": False, "spd": False}
    if not sym["symmetric"]:
        return rep
    eig = np.linalg.eigvalsh(A)
    minors = [float(np.linalg.det(A[:k, :k])) for k in range(1, n + 1)]
    tol_eig = 1e-12 * max(1.0, float(np.max(np.abs(eig))))
    try:
        cholesky_decomposition(A)
        chol_ok = True
    except NotPositiveDefiniteError:
        chol_ok = False
    rep.update(
        eigenvalues=[float(v) for v in eig],
        minors=[{"k": k + 1, "det": m, "positive": bool(m > 0)} for k, m in enumerate(minors)],
        min_eig=float(eig[0]),
        max_eig=float(eig[-1]),
        eig_positive=bool(eig[0] > tol_eig),
        minors_positive=bool(all(m > 0 for m in minors)),
        cholesky_ok=chol_ok,
        spd=bool(eig[0] > tol_eig and all(m > 0 for m in minors) and chol_ok),
    )
    return rep


def condition_numbers(A: np.ndarray, precond: str) -> dict:
    """κ₂(A) y κ₂ del sistema precondicionado M^(-1/2)·A·M^(-1/2)."""
    kA = float(np.linalg.cond(A, 2))
    if precond == "jacobi":
        dinv = 1.0 / np.sqrt(np.diag(A))
        S = dinv[:, None] * A * dinv[None, :]
        S = (S + S.T) / 2.0
        ev = np.linalg.eigvalsh(S)
        kM = float(np.linalg.cond(S, 2))
    else:
        ev = np.linalg.eigvalsh((A + A.T) / 2.0)
        kM = kA
    return {
        "kappa_A": kA,
        "kappa_M": kM,
        "ratio": kA / kM if kM > 0 else None,
        "precond_eigenvalues": [float(v) for v in ev],
        "precond_applied": precond == "jacobi",
    }


def error_table(x_calc, x_ref) -> list:
    """Ea, Er y Ep por componente. Si x_ref[i] = 0 el error relativo no está definido."""
    out = []
    for i, (xc, xr) in enumerate(zip(x_calc, x_ref)):
        ea = abs(float(xc) - float(xr))
        if abs(xr) < 1e-300:
            er = ep = None
        else:
            er = ea / abs(xr)
            ep = er * 100.0
        out.append({"i": i + 1, "x_calc": float(xc), "x_ref": float(xr), "ea": ea, "er": er, "ep": ep})
    return out

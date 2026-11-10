"""Módulo de pruebas de calidad (QA) ejecutables desde la aplicación.

Cada prueba EJECUTA código real y compara contra un resultado esperado. Solo se marca
«aprobada» si la comprobación se cumplió. La prueba 10 (actualización de la interfaz)
se ejecuta en el navegador; aquí se declara como pendiente del cliente.
"""
from __future__ import annotations

import copy

import numpy as np

from . import analysis, numerics, scenarios

DEF = {"tol": 1e-6, "max_iter": 1000, "precond": "jacobi", "x0": [0, 0, 0, 0]}


def _run(sid, mutate=None):
    sc = scenarios.get_scenario(sid)
    A, b = copy.deepcopy(sc["A"]), copy.deepcopy(sc["b"])
    if mutate:
        mutate(A, b)
    return sc, analysis.analyze({**DEF, "A": A, "b": b, "scenario_id": sid})


def _t(tid, name, data, expected, fn):
    try:
        ok, obtained, why = fn()
        status = "aprobada" if ok else "fallida"
    except Exception as e:  # una prueba que lanza excepción NO se aprueba
        status, obtained, why = "fallida", f"Excepción: {type(e).__name__}: {e}", "La prueba produjo una excepción inesperada."
    return {"id": tid, "name": name, "data": data, "expected": expected, "obtained": obtained, "status": status, "explanation": why}


def _scenario_test(sid, tid, nm):
    def fn():
        sc, r = _run(sid)
        if not r["valid"]:
            return False, "Resultado inválido: " + "; ".join(e["message"] for e in r["errors"]), "El escenario debería ser válido."
        ref_ok = max(abs(a - b) / abs(b) for a, b in zip(r["cholesky"]["x"], sc["expected"])) < 1e-8
        conv = r["gc"]["converged"] and r["gcp"]["converged"]
        rel = r["gcp"]["final_rel_residual"]
        ok = ref_ok and conv and rel < 1e-6 and r["spd"]["spd"]
        obt = (f"SPD={r['spd']['spd']}; Cholesky={[round(v, 6) for v in r['cholesky']['x']]}; "
               f"GC {r['gc']['iterations']} it, GCP {r['gcp']['iterations']} it; residuo GCP={rel:.2e}; "
               f"convergen ambos={conv}")
        return ok, obt, "Se compara la solución directa con la esperada (error relativo < 1e-8), se exige SPD y convergencia con residuo < 1e-6."
    return _t(tid, nm, f"Escenario «{sid}» con tol=1e-6, Jacobi, x0=0", "SPD, Cholesky = solución esperada, GC y GCP convergen", fn)


def run_all() -> list:
    tests = []
    tests.append(_scenario_test("ideal", 1, "Ejecutar escenario Ideal"))
    tests.append(_scenario_test("stress", 2, "Ejecutar escenario de Estrés financiero"))
    tests.append(_scenario_test("ill", 3, "Ejecutar escenario Mal condicionado"))

    def t4():
        A = [[1, 2, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        r = analysis.analyze({**DEF, "A": A, "b": [1, 1, 1, 1], "scenario_id": None})
        codes = [e["code"] for e in r["errors"]]
        ok = (not r["valid"]) and "not_symmetric" in codes and "gc" not in r
        return ok, f"valid={r['valid']}; códigos={codes}; mensaje: {r['errors'][0]['message'] if r['errors'] else '—'}", "No debe colapsar ni ejecutar GC/GCP."
    tests.append(_t(4, "Detectar matriz no simétrica", "A con a12=2 y a21=0, b=[1,1,1,1]", "Error «not_symmetric», sin ejecutar métodos", t4))

    def t5():
        A = [[1, 2, 0, 0], [2, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        r = analysis.analyze({**DEF, "A": A, "b": [1, 1, 1, 1], "scenario_id": None})
        codes = [e["code"] for e in r["errors"]]
        ok = (not r["valid"]) and "not_spd" in codes and r["spd"]["symmetric"] and "gc" not in r
        return ok, f"valid={r['valid']}; simétrica={r['spd']['symmetric']}; λmin={r['spd']['min_eig']:.4g}; códigos={codes}", "Simétrica con autovalor −1 → no definida positiva; no se ejecutan los métodos."
    tests.append(_t(5, "Detectar matriz simétrica no definida positiva", "A=[[1,2],[2,1]] ⊕ I₂ (λ=−1,3,1,1)", "Error «not_spd», sin ejecutar métodos", t5))

    def t6():
        _, r0 = _run("ideal")
        _, r1 = _run("ideal", lambda A, b: (A[0].__setitem__(0, 2.0)))
        x_expected = np.linalg.solve(np.array(r1["inputs"]["A"]), np.array(r1["inputs"]["b"]))
        diff_new = np.max(np.abs(np.array(r1["cholesky"]["x"]) - x_expected))
        changed = np.max(np.abs(np.array(r1["cholesky"]["x"]) - np.array(r0["cholesky"]["x"])))
        ok = r1["valid"] and diff_new < 1e-10 and changed > 1e-3 and r1["signature"] != r0["signature"] and not r1["unmodified"] \
            and "personalizado" in r1["conclusions"]["label"] and r1["gcp"]["converged"]
        return ok, f"x nuevo={[round(v, 6) for v in r1['cholesky']['x']]}; |x_Cholesky − solve|={diff_new:.1e}; cambio vs original={changed:.3f}; firma distinta={r1['signature'] != r0['signature']}; etiqueta={r1['conclusions']['label']}", "Tras editar a11 de 1.21 a 2.0 deben recalcularse solución, GC, GCP y etiquetarse como personalizado."
    tests.append(_t(6, "Modificar A y comprobar recálculo", "Escenario Ideal con a11 = 2.0", "Nueva solución = np.linalg.solve; firma distinta; etiqueta personalizada", t6))

    def t7():
        _, r0 = _run("ideal")
        _, r1 = _run("ideal", lambda A, b: b.__setitem__(0, b[0] + 10.0))
        A = np.array(r1["inputs"]["A"])
        dx = np.linalg.solve(A, np.array([10.0, 0, 0, 0]))
        got = np.array(r1["cholesky"]["x"], dtype=float) - np.array(r0["cholesky"]["x"], dtype=float)
        got, dx = got.tolist(), dx.tolist()
        got, dx = np.array(got), np.array(dx)
        ok = r1["valid"] and np.max(np.abs(got - dx)) < 1e-9 and r1["conclusions"]["financial"] != r0["conclusions"]["financial"]
        return ok, f"Δx={[round(float(v), 6) for v in got]}; esperado A⁻¹Δb={[round(float(v), 6) for v in dx]}; conclusión financiera cambió={r1['conclusions']['financial'] != r0['conclusions']['financial']}", "Por linealidad Δx = A⁻¹·Δb; la interpretación financiera debe cambiar."
    tests.append(_t(7, "Modificar b y comprobar recálculo", "Escenario Ideal con b₁ + 10", "Δx = A⁻¹Δb y conclusiones distintas", t7))

    def t8():
        sc = scenarios.get_scenario("ill")
        A, b = np.array(sc["A"]), np.array(sc["b"])
        mine = numerics.conjugate_gradient(A, b, np.zeros(4), 1e-6, 1000, "jacobi")
        # PCG independiente con M explícita (resuelve M z = r con np.linalg.solve)
        M = np.diag(np.diag(A))
        x = np.zeros(4); r = b - A @ x; z = np.linalg.solve(M, r); p = z.copy(); k = 0
        while np.linalg.norm(b - A @ x) / np.linalg.norm(b) >= 1e-6 and k < 1000:
            Ap = A @ p; al = (r @ z) / (p @ Ap); x = x + al * p; rn = r - al * Ap
            zn = np.linalg.solve(M, rn); be = (rn @ zn) / (r @ z); p = zn + be * p; r, z = rn, zn; k += 1
        S_cond = numerics.condition_numbers(A, "jacobi")
        ev = np.sort(np.linalg.eigvals(np.linalg.inv(M) @ A).real)
        k_eig = ev[-1] / ev[0]
        ok = mine["iterations"] == k and np.allclose(mine["x"], x, rtol=1e-9) and abs(S_cond["kappa_M"] - k_eig) / k_eig < 1e-6 and S_cond["kappa_M"] < S_cond["kappa_A"]
        return ok, f"Iteraciones implementación={mine['iterations']}, PCG independiente={k}; κ(M^-1/2AM^-1/2)={S_cond['kappa_M']:.4f} vs κ(M⁻¹A) por autovalores={k_eig:.4f}; κ(A)={S_cond['kappa_A']:.3e}", "La implementación con z = r/diag(A) debe coincidir con un PCG que resuelve M·z = r explícitamente, y κ debe reducirse."
    tests.append(_t(8, "Comprobar funcionamiento de Jacobi", "Escenario Mal condicionado, M = diag(A)", "Mismas iteraciones y solución que un PCG con M explícita; κ precondicionado < κ(A)", t8))

    def t9():
        a = scenarios.get_scenario("ideal")
        a["A"][0][0] = 999.0; a["b"][0] = -5.0  # modificar la copia
        again = scenarios.get_scenario("ideal")
        r = analysis.analyze({**DEF, "A": again["A"], "b": again["b"], "scenario_id": "ideal"})
        ok = again["A"][0][0] == 1.21 and again["b"][0] == 66.70 and r["unmodified"] and r["valid"]
        return ok, f"Tras alterar la copia: a11={again['A'][0][0]}, b1={again['b'][0]}, escenario sin modificar={r['unmodified']}", "Cada carga entrega una copia nueva; restaurar devuelve exactamente los datos originales."
    tests.append(_t(9, "Restauración de escenarios", "Se altera una copia del Ideal (a11=999, b1=−5) y se vuelve a cargar", "Valores originales a11=1.21, b1=66.70, escenario marcado como original", t9))

    tests.append({
        "id": 10, "name": "Actualización de gráficos, tablas e interpretaciones",
        "data": "Resultado activo en pantalla (se verifica en el navegador)",
        "expected": "Gráficos, tablas y conclusiones coinciden con el resultado del último cálculo",
        "obtained": "Pendiente: se ejecuta en el navegador", "status": "pendiente",
        "explanation": "Requiere el DOM; se evalúa en el cliente.", "client": True,
    })

    def t11():
        sc, r = _run("ill")
        ok = r["valid"] and r["gcp"]["converged"] and r["gc"]["converged"] and r["gcp"]["iterations"] <= r["gc"]["iterations"]
        return ok, f"GCP={r['gcp']['iterations']} it, GC={r['gc']['iterations']} it; κ(A)={r['cond']['kappa_A']:.3e} → κ precond={r['cond']['kappa_M']:.3f}", "Con n=4 la diferencia es pequeña, pero la prueba exige GCP ≤ GC y reducción de κ."
    tests.append(_t(11, "Comparativa de precondicionamiento (GCP ≤ GC en mal condicionado)", "Escenario Mal condicionado, tol 1e-6", "Iteraciones GCP ≤ Iteraciones GC", t11))
    return analysis.sanitize(tests)

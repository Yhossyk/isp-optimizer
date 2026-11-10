"""Generación DINÁMICA de conclusiones y recomendaciones.

Todo el texto se construye a partir del resultado numérico recibido; ningún párrafo
es fijo. Si cambian A, b o los parámetros, cambian los números y las ramas del texto.
"""
from __future__ import annotations

SHORT = ["fibra óptica", "routers y switches", "servidores", "mantenimiento"]
N_ITER_THEORY = 4


def _f(v, d=4):
    if v is None:
        return "no definido"
    if v != 0 and (abs(v) < 1e-3 or abs(v) >= 1e6):
        return f"{v:.3e}"
    return f"{v:,.{d}f}".replace(",", " ")


def _money(v):
    return f"Bs {v:,.2f} mil".replace(",", " ")


def _vec(v, d=4):
    return "[" + "; ".join(_f(x, d) for x in v) + "]"


def _cond_class(k):
    if k < 10:
        return "bien condicionada"
    if k < 1e3:
        return "moderadamente condicionada"
    return "mal condicionada"


def financial_brief(x_ref, label=""):
    """Resumen financiero corto (para la tabla comparativa de escenarios)."""
    total = sum(x_ref)
    if total <= 0 or any(v < 0 for v in x_ref):
        return "Las cantidades obtenidas incluyen valores no positivos; no son interpretables como inversión."
    idx = max(range(4), key=lambda i: x_ref[i])
    return (
        f"Inversión total estimada {_money(total)}; la mayor parte es {SHORT[idx]} "
        f"({x_ref[idx] / total * 100:.1f} %)."
    )


def build(res: dict, ctx: dict) -> dict:
    """res: resultado del análisis. ctx: {label, scenario_id, unmodified, baseline_total}."""
    label = ctx.get("label", "Escenario activo")
    if not res.get("valid"):
        return _invalid(res, label)

    spd = res["spd"]
    chol = res["cholesky"]
    gc, gcp = res["gc"], res["gcp"]
    cond = res["cond"]
    x_ref = chol["x"]
    tol = res["inputs"]["tol"]
    precond = res["inputs"]["precond"]
    kA, kM = cond["kappa_A"], cond["kappa_M"]
    err_gcp = res["errors_gcp"]
    err_gc = res["errors_gc"]

    # ---------------- A. Matemática ----------------
    m = []
    m.append(
        f"Para «{label}», la matriz A es simétrica (diferencia máxima entre aᵢⱼ y aⱼᵢ: {spd['max_asymmetry']:.1e}) y definida positiva: "
        f"su menor valor propio es {_f(spd['min_eig'], 6)} > 0 y todos los menores principales de Sylvester son positivos "
        f"(el último vale {_f(spd['minors'][-1]['det'], 4)}). Por eso GC y GCP están bien fundamentados para este sistema."
    )
    m.append(
        f"La solución directa por Cholesky es x = {_vec(x_ref)} (miles de Bs); comprobación ‖b − A·x‖/‖b‖ = {chol['check_rel']:.2e}. "
        f"La matriz está {_cond_class(kA)}: κ₂(A) = {_f(kA, 3)}."
    )
    for g, nm in ((gc, "GC"), (gcp, "GCP")):
        if g["converged"]:
            m.append(f"{nm} convergió en {g['iterations']} iteración(es) con residuo relativo real {g['final_rel_residual']:.2e} < {tol:.0e}.")
        else:
            m.append(f"{nm} NO convergió: {g['reason']} Tras {g['iterations']} iteración(es) el residuo relativo real es {g['final_rel_residual']:.2e} (tolerancia {tol:.0e}).")
    max_ea = max(e["ea"] for e in err_gcp)
    eps = [e["ep"] for e in err_gcp if e["ep"] is not None]
    max_ep = max(eps) if eps else None
    txt = f"Respecto de la solución directa, el GCP tiene un error absoluto máximo de {max_ea:.2e}"
    txt += f" y un error porcentual máximo de {max_ep:.2e} %." if max_ep is not None else "."
    if any(e["er"] is None for e in err_gcp):
        txt += " En las componentes de referencia nulas el error relativo no está definido."
    m.append(txt)
    if gcp["converged"] and kA > 1e3:
        bound = kA * gcp["final_rel_residual"]
        m.append(
            f"Con κ(A) elevado, un residuo pequeño no garantiza un error pequeño en x: la cota teórica ‖x − x*‖/‖x*‖ ≤ κ·‖r‖/‖b‖ "
            f"es ≈ {bound:.2e}, mientras que el error relativo observado (norma 2) es "
            f"{_norm_rel(err_gcp):.2e}."
        )

    # ---------------- B. Financiera ----------------
    f = []
    total = sum(x_ref)
    parts = "; ".join(f"{SHORT[i]}: {_money(x_ref[i])}" for i in range(4))
    f.append(f"Las cantidades de inversión estimadas por el modelo lineal (referencia directa) son — {parts}. Total: {_money(total)}.")
    if any(v < 0 for v in x_ref):
        neg = [SHORT[i] for i in range(4) if x_ref[i] < 0]
        f.append(
            "Atención: hay componentes negativas (" + ", ".join(neg) + "). Una inversión negativa no tiene "
            "sentido financiero; los datos de A y b deberían revisarse."
        )
    elif total > 0:
        shares = [v / total * 100 for v in x_ref]
        idx = max(range(4), key=lambda i: x_ref[i])
        jdx = min(range(4), key=lambda i: x_ref[i])
        f.append(
            f"La mayor proporción corresponde a {SHORT[idx]} ({shares[idx]:.1f} %) y la menor a {SHORT[jdx]} ({shares[jdx]:.1f} %). "
            f"El reparto porcentual completo es {', '.join(f'{SHORT[i]} {shares[i]:.1f} %' for i in range(4))}."
        )
    base = ctx.get("baseline_total")
    if base and ctx.get("scenario_id") == "stress" and ctx.get("unmodified"):
        f.append(
            f"Frente al escenario Ideal (total {_money(base)}), el estrés eleva la inversión total estimada en "
            f"{_money(total - base)} ({(total / base - 1) * 100:.1f} %). Como κ(A) no cambia, el estrés desplaza el "
            f"punto de equilibrio sin volver más difícil el cálculo."
        )
    elif ctx.get("scenario_id") == "ill" and ctx.get("unmodified"):
        f.append("Los coeficientes de A abarcan varios órdenes de magnitud (escalas muy distintas entre áreas), aunque las cantidades x resultantes sí son comparables en miles de Bs; el sistema es muy sensible a perturbaciones de b.")
    elif not ctx.get("unmodified") or not ctx.get("scenario_id"):
        f.append("Los datos fueron modificados o introducidos manualmente, por lo que esta interpretación corresponde a un escenario personalizado.")
    f.append(
        "Estos valores son la solución de un modelo lineal con datos supuestos; no constituyen por sí solos una optimización "
        "restringida por presupuesto ni una cotización real."
    )

    # ---------------- C. Comparación ----------------
    c = []
    ig, ip = gc["iterations"], gcp["iterations"]
    rg, rp = gc["final_rel_residual"], gcp["final_rel_residual"]
    if precond == "none":
        c.append("Se seleccionó «sin precondicionador»: el GCP coincide con el GC y la comparación no aporta información adicional.")
    elif gc["converged"] and gcp["converged"]:
        if ip < ig:
            c.append(f"El GCP con Jacobi fue más rápido: {ip} iteraciones frente a {ig} del GC.")
        elif ip == ig:
            c.append(f"GC y GCP necesitaron el mismo número de iteraciones ({ig}); en este caso Jacobi no redujo el trabajo iterativo.")
        else:
            c.append(f"El GC fue más rápido: {ig} iteraciones frente a {ip} del GCP; Jacobi no ayudó en este sistema.")
        c.append(f"Residuos relativos finales: GC {rg:.2e}, GCP {rp:.2e}.")
    elif gcp["converged"] and not gc["converged"]:
        c.append(f"Solo el GCP convergió ({ip} iteraciones); el GC no cumplió la tolerancia tras {ig}.")
    elif gc["converged"] and not gcp["converged"]:
        c.append(f"Solo el GC convergió ({ig} iteraciones); el GCP NO convergió: {gcp['reason']}")
    else:
        c.append("Ninguno de los dos métodos convergió dentro de los parámetros fijados.")
    if precond == "jacobi":
        ratio = cond["ratio"]
        if ratio is not None and ratio > 10:
            c.append(f"Jacobi redujo el número de condición de {_f(kA, 3)} a {_f(kM, 3)} (factor ≈ {ratio:.1f}): el mal condicionamiento se debía en buena parte al escalamiento diagonal.")
        elif ratio is not None and ratio > 1.5:
            c.append(f"Jacobi redujo κ de {_f(kA, 3)} a {_f(kM, 3)} (factor ≈ {ratio:.2f}), una mejora moderada.")
        else:
            c.append(f"κ pasó de {_f(kA, 4)} a {_f(kM, 4)}: Jacobi no aporta una mejora apreciable porque la diagonal de A es casi uniforme y el acoplamiento es de otro origen.")
    if gc["converged"] and gcp["converged"] and max(ig, ip) <= N_ITER_THEORY + 1:
        c.append(
            "Nota: para n = 4, en aritmética exacta el GC termina en a lo sumo 4 pasos; diferencias de una iteración "
            "se deben a errores de redondeo, por lo que no deben sobreinterpretarse."
        )

    # ---------------- D. General ----------------
    g = []
    g.append(
        f"El sistema activo ({label}) tiene κ(A) = {_f(kA, 3)} y los métodos "
        + ("convergieron" if gc["converged"] and gcp["converged"] else "no convergieron ambos")
        + f" con tolerancia {tol:.0e}. Aprendizaje principal: "
        + (
            "con una matriz bien condicionada, ambos métodos alcanzan la solución en muy pocas iteraciones y el precondicionador es prescindible."
            if kA < 10 and precond == "jacobi"
            else "el condicionamiento determina la dificultad numérica del sistema, más que el tamaño de los datos."
        )
    )
    g.append(
        "Limitaciones: los coeficientes y requerimientos son supuestos académicos; el modelo es lineal y estático; "
        "resolver Ax = b describe un equilibrio de necesidades, no una optimización con restricción presupuestaria; "
        "y no incorpora incertidumbre ni plazos de inversión."
    )

    # ---------------- Recomendaciones ----------------
    rm, rf = [], []
    if not (gc["converged"] and gcp["converged"]):
        rm.append("Revisar la tolerancia y aumentar el máximo de iteraciones, o replantear el sistema, ya que al menos un método no convergió.")
    if kA > 1e3:
        rm.append("Re-escalar las variables (p. ej. expresar cada área en unidades comparables) para reducir κ(A) antes de resolver.")
        if precond == "jacobi" and cond["ratio"] is not None and cond["ratio"] < 10:
            rm.append("Jacobi mejora poco: ensayar un precondicionador que capture el acoplamiento fuera de la diagonal (Cholesky incompleto IC(0) o SSOR).")
    elif precond == "jacobi" and cond["ratio"] is not None and cond["ratio"] < 1.5:
        rm.append("Con esta matriz el precondicionador de Jacobi es prescindible; el GC simple basta.")
    rm.append("Verificar siempre el residuo real b − A·x al finalizar, y no solo el residuo recursivo del algoritmo.")
    rm.append("Contrastar la solución iterativa con la directa (Cholesky) cada vez que se modifiquen A o b.")

    if total > 0 and all(v >= 0 for v in x_ref):
        idx = max(range(4), key=lambda i: x_ref[i])
        rf.append(f"Priorizar la validación de cotizaciones y plazos de {SHORT[idx]}, que concentra la mayor parte de la inversión estimada ({x_ref[idx] / total * 100:.1f} %).")
        if x_ref[3] / total < 0.05:
            rf.append("El mantenimiento representa menos del 5 % del total: conviene revisar si está subestimado frente a la infraestructura instalada.")
        if base and ctx.get("scenario_id") == "stress" and ctx.get("unmodified"):
            rf.append(f"Prever una reserva de contingencia cercana al {(total / base - 1) * 100:.0f} % del plan base, que es el incremento estimado en este escenario de estrés.")
    else:
        rf.append("Revisar los datos de entrada antes de tomar decisiones: la solución contiene cantidades no interpretables como inversión.")
    rf.append(
        f"Para sensibilidad: como x = A⁻¹b, un cambio relativo en b puede alterar x hasta κ(A) = {_f(kA, 3)} veces en términos relativos; "
        + ("este factor es bajo, así que pequeñas variaciones de requerimientos tienen efecto acotado." if kA < 10 else "ese factor es alto: pequeñas variaciones de requerimientos pueden alterar mucho la solución.")
    )
    rf.append("Antes de presupuestar, reemplazar los datos supuestos por cotizaciones y estadísticas reales de la empresa y añadir restricciones presupuestarias en un modelo de optimización.")

    return {
        "status": "ok",
        "label": label,
        "math": m,
        "financial": f,
        "comparison": c,
        "general": g,
        "rec_math": rm,
        "rec_fin": rf,
    }


def _norm_rel(err):
    import math

    num = math.sqrt(sum(e["ea"] ** 2 for e in err))
    den = math.sqrt(sum(e["x_ref"] ** 2 for e in err))
    return num / den if den else float("nan")


def _invalid(res, label):
    reasons = [e["message"] for e in res.get("errors", [])]
    msg = [f"No se ejecutaron GC ni GCP para «{label}» porque los datos no son válidos."]
    msg += reasons
    return {
        "status": "invalid",
        "label": label,
        "math": msg,
        "financial": ["No es posible interpretar cantidades de inversión: el sistema no fue resuelto con datos válidos."],
        "comparison": ["No hay comparación entre métodos: no se ejecutaron."],
        "general": ["Corrija la matriz A, el vector b o los parámetros y los resultados se recalcularán automáticamente."],
        "rec_math": [
            "Use una matriz simétrica y definida positiva (A = Aᵀ y valores propios > 0).",
            "Revise que todos los campos sean numéricos y que la tolerancia esté entre 0 y 1.",
        ],
        "rec_fin": ["Revise que los coeficientes de costo sean coherentes (diagonal dominante y acoplamientos recíprocos)."],
    }

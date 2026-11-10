"""Persistencia SQLite: escenarios guardados e historial de simulaciones.

La base de datos solo REGISTRA datos de entrada y resultados ya calculados.
Nunca sustituye a los cálculos: al recargar un registro, la aplicación vuelve a calcular.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.environ.get(
    "ISP_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance", "isp_optimizer.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS saved_scenarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    base_scenario TEXT,
    a_json      TEXT NOT NULL,
    b_json      TEXT NOT NULL,
    x0_json     TEXT NOT NULL,
    tol         REAL NOT NULL,
    max_iter    INTEGER NOT NULL,
    precond     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS simulations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    label         TEXT NOT NULL,
    scenario_id   TEXT,
    unmodified    INTEGER NOT NULL,
    a_json        TEXT NOT NULL,
    b_json        TEXT NOT NULL,
    x0_json       TEXT NOT NULL,
    tol           REAL NOT NULL,
    max_iter      INTEGER NOT NULL,
    precond       TEXT NOT NULL,
    signature     TEXT NOT NULL,
    x_ref_json    TEXT NOT NULL,
    x_gc_json     TEXT NOT NULL,
    x_gcp_json    TEXT NOT NULL,
    it_gc         INTEGER NOT NULL,
    it_gcp        INTEGER NOT NULL,
    conv_gc       INTEGER NOT NULL,
    conv_gcp      INTEGER NOT NULL,
    rel_gc        REAL,
    rel_gcp       REAL,
    kappa_a       REAL,
    kappa_m       REAL
);
"""


@contextmanager
def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------- Simulaciones ----------------
def save_simulation(res: dict) -> int:
    """Guarda una simulación válida (ya calculada)."""
    inp = res["inputs"]
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO simulations
            (created_at,label,scenario_id,unmodified,a_json,b_json,x0_json,tol,max_iter,precond,signature,
             x_ref_json,x_gc_json,x_gcp_json,it_gc,it_gcp,conv_gc,conv_gcp,rel_gc,rel_gcp,kappa_a,kappa_m)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                _now(), res["conclusions"]["label"], res.get("scenario_id"), int(bool(res.get("unmodified"))),
                json.dumps(inp["A"]), json.dumps(inp["b"]), json.dumps(inp["x0"]),
                inp["tol"], inp["max_iter"], inp["precond"], res["signature"],
                json.dumps(res["cholesky"]["x"]), json.dumps(res["gc"]["x"]), json.dumps(res["gcp"]["x"]),
                res["gc"]["iterations"], res["gcp"]["iterations"],
                int(res["gc"]["converged"]), int(res["gcp"]["converged"]),
                res["gc"]["final_rel_residual"], res["gcp"]["final_rel_residual"],
                res["cond"]["kappa_A"], res["cond"]["kappa_M"],
            ),
        )
        return cur.lastrowid


def _sim_row(r):
    d = dict(r)
    for k in ("a_json", "b_json", "x0_json", "x_ref_json", "x_gc_json", "x_gcp_json"):
        d[k[:-5]] = json.loads(d.pop(k))
    d["unmodified"] = bool(d["unmodified"])
    d["conv_gc"] = bool(d["conv_gc"])
    d["conv_gcp"] = bool(d["conv_gcp"])
    return d


def list_simulations(limit=50):
    with _conn() as c:
        rows = c.execute("SELECT * FROM simulations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_sim_row(r) for r in rows]


def delete_simulation(sim_id: int) -> bool:
    with _conn() as c:
        return c.execute("DELETE FROM simulations WHERE id=?", (sim_id,)).rowcount > 0


def clear_simulations():
    with _conn() as c:
        c.execute("DELETE FROM simulations")


# ---------------- Escenarios guardados ----------------
def save_scenario(name, base, inp) -> int:
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO saved_scenarios (name,base_scenario,a_json,b_json,x0_json,tol,max_iter,precond,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (name, base, json.dumps(inp["A"]), json.dumps(inp["b"]), json.dumps(inp["x0"]),
             inp["tol"], inp["max_iter"], inp["precond"], _now()),
        )
        return cur.lastrowid


def list_scenarios():
    with _conn() as c:
        rows = c.execute("SELECT * FROM saved_scenarios ORDER BY id DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("a_json", "b_json", "x0_json"):
            d[k[:-5]] = json.loads(d.pop(k))
        out.append(d)
    return out


def delete_scenario(sid: int) -> bool:
    with _conn() as c:
        return c.execute("DELETE FROM saved_scenarios WHERE id=?", (sid,)).rowcount > 0

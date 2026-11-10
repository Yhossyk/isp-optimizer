"""ISP OPTIMIZER · aplicación Flask (rutas HTTP). La lógica vive en backend/."""
from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from backend import analysis, database, qa, scenarios, validation


def create_app() -> Flask:
    app = Flask(__name__)
    database.init_db()

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            student=os.environ.get("STUDENT_NAME", "Yhoselyn Karem Carrillo Mamani"),
            teacher=os.environ.get("TEACHER_NAME", "Lic. Brigida Alexandra Carvajal Blanco"),
        )

    @app.get("/api/scenarios")
    def api_scenarios():
        return jsonify({
            "scenarios": scenarios.all_scenarios(),
            "variables": scenarios.VARIABLES,
            "defaults": validation.DEFAULTS,
            "properties": analysis.scenario_properties(),
        })

    @app.post("/api/analyze")
    def api_analyze():
        payload = request.get_json(silent=True) or {}
        res = analysis.analyze(payload)
        if payload.get("save") and res.get("valid"):
            res["saved_id"] = database.save_simulation(res)
        return jsonify(res)

    @app.post("/api/compare")
    def api_compare():
        return jsonify(analysis.compare_scenarios(request.get_json(silent=True) or {}))

    @app.post("/api/qa/run")
    def api_qa():
        return jsonify(qa.run_all())

    @app.get("/api/history")
    def api_history():
        return jsonify(database.list_simulations())

    @app.delete("/api/history")
    def api_history_clear():
        database.clear_simulations()
        return jsonify({"ok": True})

    @app.delete("/api/history/<int:sim_id>")
    def api_history_delete(sim_id):
        return jsonify({"ok": database.delete_simulation(sim_id)})

    @app.get("/api/saved")
    def api_saved():
        return jsonify(database.list_scenarios())

    @app.post("/api/saved")
    def api_saved_create():
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name", "")).strip()[:80]
        if not name:
            return jsonify({"ok": False, "errors": [{"code": "name", "message": "Escriba un nombre para el escenario."}]}), 400
        inp, errs = validation.parse_inputs(payload)
        if errs:
            return jsonify({"ok": False, "errors": errs}), 400
        data = {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in inp.items()}
        sid = database.save_scenario(name, payload.get("scenario_id"), data)
        return jsonify({"ok": True, "id": sid})

    @app.delete("/api/saved/<int:sid>")
    def api_saved_delete(sid):
        return jsonify({"ok": database.delete_scenario(sid)})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=bool(os.environ.get("FLASK_DEBUG")))

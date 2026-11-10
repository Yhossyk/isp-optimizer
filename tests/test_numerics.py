"""Pruebas automáticas (unittest). Ejecutar:  python -m unittest discover -s tests -v"""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["ISP_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import numpy as np
from backend import analysis, numerics, qa, scenarios

PARAMS = {"tol": 1e-6, "max_iter": 1000, "precond": "jacobi", "x0": [0, 0, 0, 0]}


class TestScenarios(unittest.TestCase):
    def test_reference_solutions(self):
        for sc in scenarios.all_scenarios():
            A, b = np.array(sc["A"]), np.array(sc["b"])
            self.assertTrue(np.allclose(A, A.T))
            self.assertGreater(np.linalg.eigvalsh(A)[0], 0)
            x = numerics.cholesky_solve(A, b)["x"]
            self.assertTrue(np.allclose(x, sc["expected"], rtol=1e-10), sc["id"])
            self.assertLess(np.max(np.abs(A @ np.array(sc["expected"]) - b)), 1e-9)

    def test_cholesky_matches_numpy(self):
        rng = np.random.default_rng(0)
        M = rng.normal(size=(4, 4)); A = M @ M.T + 4 * np.eye(4); b = rng.normal(size=4)
        self.assertTrue(np.allclose(numerics.cholesky_solve(A, b)["x"], np.linalg.solve(A, b)))

    def test_cg_converges_and_true_residual(self):
        for sc in scenarios.all_scenarios():
            A, b = np.array(sc["A"]), np.array(sc["b"])
            for pre in ("none", "jacobi"):
                r = numerics.conjugate_gradient(A, b, np.zeros(4), 1e-6, 1000, pre)
                self.assertTrue(r["converged"])
                true_rel = np.linalg.norm(b - A @ r["x"]) / np.linalg.norm(b)
                self.assertAlmostEqual(true_rel, r["final_rel_residual"], places=12)
                self.assertLess(true_rel, 1e-6)

    def test_max_iter_not_false_convergence(self):
        sc = scenarios.get_scenario("ill")
        r = numerics.conjugate_gradient(np.array(sc["A"]), np.array(sc["b"]), np.zeros(4), 1e-12, 1, "none")
        self.assertFalse(r["converged"])

    def test_condition_numbers(self):
        A = np.array(scenarios.get_scenario("ill")["A"])
        c = numerics.condition_numbers(A, "jacobi")
        self.assertGreater(c["kappa_A"], 1e5)
        self.assertLess(c["kappa_M"], 10)

    def test_error_table_zero_reference(self):
        t = numerics.error_table([1.0, 2.0], [0.0, 2.0])
        self.assertIsNone(t[0]["er"]); self.assertIsNone(t[0]["ep"]); self.assertEqual(t[1]["ea"], 0)


class TestValidation(unittest.TestCase):
    def test_invalid_inputs_do_not_crash(self):
        I = np.eye(4).tolist()
        cases = [
            {"A": [[1, 2], [3, 4]], "b": [1, 1, 1, 1]},
            {"A": I, "b": [1, 1, None, 1]},
            {"A": I, "b": [0, 0, 0, 0]},
            {"A": I, "b": [1, 1, 1, 1], "tol": 5},
            {"A": I, "b": [1, 1, 1, 1], "max_iter": 0},
            {"A": [[1, 0, 0, 0], [1, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], "b": [1] * 4},  # no simétrica
            {"A": [[1, 2, 0, 0], [2, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], "b": [1] * 4},  # no SPD
            {},
        ]
        for c in cases:
            r = analysis.analyze(c)
            self.assertFalse(r["valid"]); self.assertTrue(r["errors"]); self.assertNotIn("gc", r)

    def test_dynamic_conclusions_change(self):
        sc = scenarios.get_scenario("ideal")
        r1 = analysis.analyze({**PARAMS, "A": sc["A"], "b": sc["b"], "scenario_id": "ideal"})
        b2 = list(sc["b"]); b2[0] += 20
        r2 = analysis.analyze({**PARAMS, "A": sc["A"], "b": b2, "scenario_id": "ideal"})
        self.assertNotEqual(r1["conclusions"]["financial"], r2["conclusions"]["financial"])
        self.assertIn("personalizado", r2["conclusions"]["label"])

    def test_invalid_conclusions_do_not_claim_success(self):
        r = analysis.analyze({"A": np.eye(4).tolist(), "b": [0, 0, 0, 0]})
        self.assertEqual(r["conclusions"]["status"], "invalid")
        self.assertNotIn("convergió", " ".join(r["conclusions"]["math"]))


class TestQA(unittest.TestCase):
    def test_server_side_qa_all_pass(self):
        res = qa.run_all()
        for t in res:
            if not t.get("client"):
                self.assertEqual(t["status"], "aprobada", t["name"])


if __name__ == "__main__":
    unittest.main()

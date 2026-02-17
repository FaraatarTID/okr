import unittest
from src.domain.scoring import calculate_kr_score, calculate_objective_score

class TestScoring(unittest.TestCase):
    def test_kr_numeric_linear(self):
        self.assertEqual(calculate_kr_score(50, 100, 0), 0.5)
        self.assertEqual(calculate_kr_score(75, 100, 50), 0.5)
        self.assertEqual(calculate_kr_score(0, 100, 0), 0.0)
        self.assertEqual(calculate_kr_score(100, 100, 0), 1.0)

    def test_kr_clamping(self):
        self.assertEqual(calculate_kr_score(120, 100, 0), 1.0)
        self.assertEqual(calculate_kr_score(-10, 100, 0), 0.0)

    def test_kr_boolean(self):
        self.assertEqual(calculate_kr_score(1, 1, 0, "boolean"), 1.0)
        self.assertEqual(calculate_kr_score(0, 1, 0, "boolean"), 0.0)
        self.assertEqual(calculate_kr_score(0.5, 1, 0, "boolean"), 0.0)

    def test_kr_div_zero(self):
        # target == start
        self.assertEqual(calculate_kr_score(100, 100, 100), 1.0)
        self.assertEqual(calculate_kr_score(50, 100, 100), 0.0)

    def test_objective_unweighted(self):
        scores = [0.5, 0.7, 0.9]
        self.assertAlmostEqual(calculate_objective_score(scores), 0.7)

    def test_objective_weighted(self):
        scores = [1.0, 0.0]
        weights = [1.0, 3.0]
        # (1.0*1 + 0.0*3) / 4 = 0.25
        self.assertAlmostEqual(calculate_objective_score(scores, weights, weighted=True), 0.25)

if __name__ == "__main__":
    unittest.main()

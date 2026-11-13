import unittest
from core.forecasting import predict_demand, month_to_calendar_index


class TestDemandForecasting(unittest.TestCase):

    def test_single_month(self):
        # With 1 month, it uses that month's purchase value
        history = [(2026, 6, 85.0)]
        pred = predict_demand(history)
        self.assertEqual(pred, 85.0)

    def test_two_consecutive_months_linear_regression(self):
        # Month 1 (2026-05): 80
        # Month 2 (2026-06): 95 (+15 trend)
        # Target (2026-07): 95 + 15 = 110
        history = [(2026, 5, 80.0), (2026, 6, 95.0)]
        pred = predict_demand(history)
        self.assertAlmostEqual(pred, 110.0, places=4)

    def test_non_consecutive_months(self):
        # Month indices:
        # 2026-03 (index x = 0): 50
        # 2026-05 (index x = 2): 70 (slope = +10 per month)
        # Target 2026-06 (index x = 3): 70 + 10 = 80
        history = [(2026, 3, 50.0), (2026, 5, 70.0)]
        pred = predict_demand(history)
        self.assertAlmostEqual(pred, 80.0, places=4)

    def test_clamp_at_zero_for_negative_prediction(self):
        # Trend is strongly downward:
        # Month 1: 50
        # Month 2: 10 (-40)
        # Target: 10 - 40 = -30 -> clamped at 0.0
        history = [(2026, 5, 50.0), (2026, 6, 10.0)]
        pred = predict_demand(history)
        self.assertEqual(pred, 0.0)

    def test_year_boundary_transition(self):
        # 2025-11 (x = 0): 100
        # 2025-12 (x = 1): 110
        # Target 2026-01 (x = 2): 120
        history = [(2025, 11, 100.0), (2025, 12, 110.0)]
        pred = predict_demand(history)
        self.assertAlmostEqual(pred, 120.0, places=4)


if __name__ == "__main__":
    unittest.main()

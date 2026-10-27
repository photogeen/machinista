import unittest
from app.display_budget import DisplayBudget

class DisplayBudgetTests(unittest.TestCase):
    def test_display_defers_before_clock_edge_and_resumes_in_safe_gap(self):
        budget=DisplayBudget()
        self.assertFalse(budget.available(10,10.002,True))
        self.assertTrue(budget.available(10,10.0066,True))
        budget.measured(.006)
        self.assertFalse(budget.available(10,10.004,True))
        self.assertTrue(budget.available(10,10.007,True))
        self.assertTrue(budget.available(10,10,False))

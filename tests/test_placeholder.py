import unittest

from harmony_py.harmony import Request

class TestPlaceholder(unittest.TestCase):
    """
    No tests for now. This is just a placeholder.
    """
    def test_my_placholder(self):
        self.assertTrue(True)

    def test_can_instantiate_request(self):
        req = Request()
        self.assertIsNotNone(req)

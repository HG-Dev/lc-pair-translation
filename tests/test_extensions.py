"""
Tests the functionality of extension utilities.
"""
import unittest
import docx
from langchain_pairtranslation.utils.list_extensions import center_enumerate
from tests import pytest_log

class DocxChunkingTests(unittest.TestCase):
        
    def test_center_enumerate(self):
        pytest_log.info("Test center enumeration of [1, 2, 3, 4, 5]...")
        result = [(idx, val) for idx, val in center_enumerate([1, 2, 3, 4, 5])]
        self.assertEqual(result, [(2, 3), (3, 4), (1, 2), (4, 5), (0, 1)], "Clockwise center enumeration failed.")
        result = [(idx, val) for idx, val in center_enumerate([1, 2, 3, 4, 5], clockwise=False)]
        self.assertEqual(result, [(2, 3), (1, 2), (3, 4), (0, 1), (4, 5)], "Counter-clockwise center enumeration failed.")
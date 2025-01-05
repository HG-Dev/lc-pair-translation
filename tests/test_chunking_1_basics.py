"""
Tests for basic functionality required by the chunking module.
"""
import re
from typing import Callable
import unittest
from langchain_pairtranslation.chunking.base import BaseDocumentChunks
from langchain_pairtranslation.config import SplitPattern
from langchain_pairtranslation.rowinfo import Adjacency, RowMetadata
from tests import pytest_log

class ChunkingBasics(unittest.TestCase):

    def test_row_metadata(self):
        row = RowMetadata(row_index=0, row_length=1, col_range=(0,0))
        self.assertEqual(row.col_range, (0,0))
        self.assertEqual(row.length, 0)
        self.assertEqual(row.start_col, 0)
        self.assertEqual(row.end_col, 0)
        self.assertRaises(ValueError, RowMetadata, row_index=1, row_length=1, col_range=(1,0))

    def test_row_metadata_to_text(self):
        src = "Hello, world!"
        row = RowMetadata(row_index=0, row_length=len(src), col_range=(0, 5))
        rendered = row.to_text(src)
        self.assertEqual(rendered, "Hello")

    def test_row_metadata_adjacency(self):
        src = ["Line 1", "Line 2", "Line 3"]
        metadata = [row for row in RowMetadata.from_enumerated_rows(enumerate(src))]
        self.assertEqual(metadata[0].eval_adjacency(metadata[1]), Adjacency.FORWARD)
        self.assertEqual(metadata[1].eval_adjacency(metadata[0]), Adjacency.BACKWARD)
        self.assertEqual(metadata[0].eval_adjacency(metadata[2]), Adjacency.NONE)
        line1_inside = RowMetadata(row_index=0, row_length=len(src[0]), col_range=(2, 3))
        self.assertEqual(len(line1_inside), 1)
        self.assertEqual(metadata[0].row_index, line1_inside.row_index)
        self.assertTrue((line1_inside.start_col >= metadata[0].start_col and line1_inside.start_col <= metadata[0].end_col))
        self.assertEqual(line1_inside.eval_adjacency(metadata[0]), Adjacency.OVERLAPPING)
        self.assertEqual(metadata[0].eval_adjacency(line1_inside), Adjacency.OVERLAPPING)
        self.assertEqual(metadata[1].eval_adjacency(line1_inside), Adjacency.NONE)

    def test_chunk_adjacency(self):
        src = ["Line 1", "Line 2", "Line 3"]
        metadata = [row for row in RowMetadata.from_enumerated_rows(enumerate(src))]
        chunks = BaseDocumentChunks.from_strings(src)
        for md, chunk in zip(metadata, chunks):
            self.assertEqual(md, chunk.start)

        self.assertEqual(chunks[0].eval_adjacency(chunks[1]), Adjacency.FORWARD)
        self.assertEqual(chunks[1].eval_adjacency(chunks[0]), Adjacency.BACKWARD)
        self.assertEqual(chunks[0].eval_adjacency(chunks[2]), Adjacency.NONE)

    def test_merging_chunks(self):
        src = ["Line 1", "Line 2", "Line 3"]
        chunks = BaseDocumentChunks.from_strings(src)
        chunks.merge_pass(16)
        self.assertEqual(chunks[0].start.row_index, 0)
        self.assertEqual(chunks[0].end.row_index, 1)
        self.assertEqual(len(chunks), 2)
        rows = [row for row in chunks.to_row_exports_iter(src.__getitem__, len(src))]
        self.assertEqual(rows, src)

    def test_splitting_sentence(self):
        # Split on sentence boundaries
        splitter = SplitPattern(name="End of sentence", pattern_src=r'([.!?。！？…])[^A-z0-9"]')
        src = "Hello, world. This is a test sentence."
        chunks = BaseDocumentChunks.from_strings([src])
        chunks.split_pass(lambda x: src, 16, [splitter])
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].to_text(lambda x: src), "Hello, world.")
        self.assertEqual(chunks[1].to_text(lambda x: src), "This is a test sentence.")
        self.assertTrue(chunks[1].warnings, "No warnings generated for unsplittable sentence.")
        
        rows = [row for row in chunks.to_row_exports_iter(lambda _: src, 1)]
        self.assertEqual(rows, [src])

    def test_unsplittable_sentence(self):
        # Split on sentence boundaries
        splitter = SplitPattern(name="End of sentence", pattern_src=r'([.!?。！？…])[^A-z0-9"]')
        src = "Hello, world, I have no correct position to split upon."
        chunks = BaseDocumentChunks.from_strings([src])
        chunks.split_pass(lambda x: src, 16, [splitter])
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].to_text(lambda x: src), src)
        self.assertTrue(chunks[0].warnings, "No warnings generated for unsplittable sentence.")

        rows = [row for row in chunks.to_row_exports_iter(lambda _: src, 1)]
        self.assertEqual(rows, [src])
        
    def test_export_chunks(self):
        src = ["Line 1", "Line 2", "Line 3"]
        row_getter : Callable[[int], str] = lambda idx: src[idx]

        chunks = BaseDocumentChunks.from_strings(src)

        rows = [row for row in chunks.to_row_exports_iter(row_getter, len(src))]
        self.assertEqual(rows, src)
        
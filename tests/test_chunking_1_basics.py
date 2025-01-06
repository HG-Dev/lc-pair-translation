"""
Tests for basic functionality required by the chunking module.
"""
import re
from typing import Callable
import unittest

from pydantic import ValidationError
from langchain_pairtranslation.chunking.base import BaseDocumentChunks
from langchain_pairtranslation.config import SplitPattern
from langchain_pairtranslation.rowinfo import Adjacency, ParagraphSpan
from tests import pytest_log

class ChunkingBasics(unittest.TestCase):

    def test_row_metadata(self):
        pspan = ParagraphSpan(src_index=0, src_length=1, src_breaks=[], char_range=(0,1))
        self.assertEqual(pspan.char_range, (0,1))
        self.assertEqual(pspan.length, 1)
        self.assertEqual(pspan.start, 0)
        self.assertEqual(pspan.end, 1)
        self.assertRaises(ValidationError, ParagraphSpan, src_index=1, src_length=2, src_breaks=[], char_range=(1,1))
        self.assertRaises(ValidationError, ParagraphSpan, src_index=1, src_length=1, src_breaks=[], char_range=(1,0))

    def test_row_metadata_to_text(self):
        src = "Hello, world!"
        row = ParagraphSpan(src_index=0, src_length=len(src), src_breaks=[], char_range=(0, 5))
        rendered = row.to_text(src)
        self.assertEqual(rendered, "Hello")

    def test_row_metadata_adjacency(self):
        src = ["Line 1", "Line 2", "Line 3"]
        metadata = [para for para in ParagraphSpan.from_enumerated_paragraphs(enumerate(src))]
        self.assertEqual(metadata[0].eval_adjacency(metadata[1]), Adjacency.FORWARD)
        self.assertEqual(metadata[1].eval_adjacency(metadata[0]), Adjacency.BACKWARD)
        self.assertEqual(metadata[0].eval_adjacency(metadata[2]), Adjacency.NONE)
        line1_inside = ParagraphSpan(src_index=0, src_length=len(src[0]), src_breaks=[], char_range=(2, 3))
        self.assertEqual(metadata[0].src_index, line1_inside.src_index)
        self.assertTrue((line1_inside.start >= metadata[0].start and line1_inside.start <= metadata[0].end))
        self.assertEqual(line1_inside.eval_adjacency(metadata[0]), Adjacency.OVERLAPPING)
        self.assertEqual(metadata[0].eval_adjacency(line1_inside), Adjacency.OVERLAPPING)
        self.assertEqual(metadata[1].eval_adjacency(line1_inside), Adjacency.NONE)

    def test_chunk_adjacency(self):
        src = ["Line 1", "Line 2", "Line 3"]
        metadata = [paragraph for paragraph in ParagraphSpan.from_enumerated_paragraphs(enumerate(src))]
        chunks = BaseDocumentChunks.from_paragraphs(src)
        for md, chunk in zip(metadata, chunks):
            self.assertEqual(md, chunk.start)

        self.assertEqual(chunks[0].eval_adjacency(chunks[1]), Adjacency.FORWARD)
        self.assertEqual(chunks[1].eval_adjacency(chunks[0]), Adjacency.BACKWARD)
        self.assertEqual(chunks[0].eval_adjacency(chunks[2]), Adjacency.NONE)

    def test_merging_chunks(self):
        src = ["Line 1", "Line 2", "Line 3"]
        chunks = BaseDocumentChunks.from_paragraphs(src)
        chunks.merge_pass(16)
        self.assertEqual(chunks[0].start.src_index, 0)
        self.assertEqual(chunks[0].end.src_index, 1)
        self.assertEqual(len(chunks), 2)
        pspans = [paragraph for paragraph in chunks.to_paragraph_exports_iter(src.__getitem__, len(src))]
        self.assertEqual(pspans, src)

    def test_splitting_sentence(self):
        # Split on sentence boundaries
        splitter = SplitPattern(name="End of sentence", pattern_src=r'([.!?。！？…])[^A-z0-9"]')
        src = "Hello, world. This is a test sentence."
        chunks = BaseDocumentChunks.from_paragraphs([src])
        chunks.split_pass(lambda x: src, 16, [splitter])
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].to_text(lambda x: src), "Hello, world.")
        self.assertEqual(chunks[1].to_text(lambda x: src), "This is a test sentence.")
        self.assertTrue(chunks[1].warnings, "No warnings generated for unsplittable sentence.")
        
        rows = [row for row in chunks.to_paragraph_exports_iter(lambda _: src, 1)]
        self.assertEqual(rows, [src])

    def test_unsplittable_sentence(self):
        # Split on sentence boundaries
        splitter = SplitPattern(name="End of sentence", pattern_src=r'([.!?。！？…])[^A-z0-9"]')
        src = "Hello, world, I have no correct position to split upon."
        chunks = BaseDocumentChunks.from_paragraphs([src])
        chunks.split_pass(lambda x: src, 16, [splitter])
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].to_text(lambda x: src), src)
        self.assertTrue(chunks[0].warnings, "No warnings generated for unsplittable sentence.")

        rows = [row for row in chunks.to_paragraph_exports_iter(lambda _: src, 1)]
        self.assertEqual(rows, [src])
        
    def test_export_chunks(self):
        src = ["Line 1", "Line 2", "Line 3"]
        src_getter : Callable[[int], str] = lambda idx: src[idx]

        chunks = BaseDocumentChunks.from_paragraphs(src)

        rows = [row for row in chunks.to_paragraph_exports_iter(src_getter, len(src))]
        self.assertEqual(rows, src)
        
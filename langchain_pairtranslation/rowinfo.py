from enum import Enum
from re import compile, Pattern
from typing import Iterator
from pydantic import BaseModel, Field, PositiveInt, field_validator
from functools import total_ordering

from langchain_pairtranslation.config import SplitBehavior, SplitPattern
from .utils.unsigned_int import UnsignedInt

NEWLINE_PATTERN: Pattern = compile(r"\n|\r")

class Adjacency(Enum):
    """ Enum for determining sequence adjacency. """
    NONE = 0
    FORWARD = 1
    BACKWARD = 2
    OVERLAPPING = 3
    IDENTICAL = 4

@total_ordering #TODO: Don't use total_ordering, it's reportedly slower than implementing the rest
class RowCol(BaseModel):
    """
    ### Summary
    A row and column pair representing a position in a document.
    ### Attributes
        1. row : PositiveInt
        2. column : PositiveInt
    """
    row: PositiveInt = Field(default=0)
    column: PositiveInt = Field(default=0)

    def __eq__(self, other):
        for left, right in zip(iter(self), iter(other)):
            if left != right:
                return False
        return True
    
    def __lt__(self, other):
        for left, right in zip(iter(self), iter(other)):
            if left < right:
                return True
            elif right > left:
                return False
        return False

    @staticmethod
    def zero():
        return RowCol()
    
    @classmethod
    def create(cls, row: PositiveInt, column: PositiveInt):
        return cls(row=row, column=column)
    
    def dot_str(self) -> str:
        return f'{self.row}.{self.column}'
    
    def to_tuple(self, zero_indexed = False) -> tuple[int, int]:
        if zero_indexed:
            return self.row - 1, self.column
        return self.row, self.column

    def __str__(self):
        return f"(Row {self.row}, Col {self.column})"
    
    def __iter__(self):
        yield self.row
        yield self.column

    def is_within_bounds(self, max_row, max_column):
        """Check if the coordinate is within the given bounds."""
        return 0 <= self.row < max_row and 0 <= self.column < max_column
    
class ParagraphSpan(BaseModel):
    """
    ### Summary
    Metadata defining a portion of a paragraph in a document.
    Index and char_count cannot be changed after initialization.
    ### Attributes
    1. src_index : UnsignedInt recording the paragraph index in the original document.
    2. src_length : UnsignedInt describing the length of the paragraph in the original document.
    3. src_breaks : List of UnsignedInt describing the character indices of line breaks in the paragraph.
    3. char_range : UnsignedInt tuple describing the content range from to [0] to [1] exclusive.
    """
    src_index: UnsignedInt = Field(frozen=True)
    src_length: UnsignedInt = Field(frozen=True)
    src_breaks: list[UnsignedInt] = Field(frozen=True)
    char_range: tuple[UnsignedInt, UnsignedInt] = Field(default_factory=lambda data: (0, data['src_length']))

    @field_validator('char_range')
    def check_col_range(cls, rng: tuple[UnsignedInt, UnsignedInt]):
        if rng[0] >= rng[1]: raise ValueError('The span start must be less than the end.')
        return rng

    def __len__(self) -> UnsignedInt:
        return self.src_length
    
    def __str__(self) -> str:
        return f"Row {self.src_index}[{self.start}:{self.end}]"

    @property
    def length(self) -> UnsignedInt:
        assert(isinstance(self.char_range, tuple))
        assert(self.end >= self.start)
        assert(self.end - self.start >= 0)
        return (self.end - self.start)
    
    @property
    def start(self):
        return self.char_range[0]
    
    @property
    def end(self):
        return self.char_range[1]
    
    @property
    def lines(self):
        return len([br_idx for br_idx in self.src_breaks if (br_idx >= self.start and br_idx < self.end)])
    
    @property
    def is_paragraph_start(self) -> bool:
        return self.char_range[0] == 0
    
    @property
    def is_paragraph_end(self) -> bool:
        return self.char_range[1] == self.src_length
    
    def eval_adjacency(self, other: 'ParagraphSpan') -> Adjacency:

        if self.src_index == other.src_index:
            if self.end == other.start:
                return Adjacency.FORWARD
            if self.start == other.end:
                return Adjacency.BACKWARD
            if self.char_range == other.char_range:
                return Adjacency.IDENTICAL
            if self._ranges_overlap(self.char_range, other.char_range):
                return Adjacency.OVERLAPPING
        
        # This segment ends a row; precedes the other
        if other.src_index - self.src_index == 1 and self.is_paragraph_end and other.is_paragraph_start:
            return Adjacency.FORWARD
        # This segment starts a row; succeeds the other
        if self.src_index - other.src_index == 1 and self.is_paragraph_start and other.is_paragraph_end:
            return Adjacency.BACKWARD
        
        return Adjacency.NONE

    @staticmethod
    def _ranges_overlap(range_a: tuple[int, int], range_b: tuple[int, int]) -> bool:
        """ Compares two ranges to determine if they overlap. Works for both ascending and descending ranges. """
        return range_a[0] < range_b[1] and range_b[0] < range_a[1]
    
    @staticmethod
    def _range_includes(range_outer: tuple[int, int], range_inner: tuple[int, int]) -> bool:
        """ Compares two ranges to determine if the inner range is within the outer range. """
        return range_outer[0] <= range_inner[0] and range_outer[1] >= range_inner[1]
    
    def to_text(self, src_row : str) -> str:
        """ Slices the source row to return the text within the column range. """
        try:
            assert(len(src_row) == self.src_length)
        except AssertionError:
            print(f"Row length mismatch: {len(src_row)} != {self.src_length}  row text: {src_row}")
            raise
        return src_row[self.start : self.end]
    
    @classmethod
    def from_single_paragraph(cls, src_index: int, src_text: str) -> 'ParagraphSpan':
        src_length = len(src_text)
        src_breaks = [br.start() for br in NEWLINE_PATTERN.finditer(src_text)]
        start = 0
        end = src_length
        trimmed_text = src_text.strip()
        if (len(trimmed_text) != src_length):
            # Update the span to reflect the trimmed text
            start = src_text.index(trimmed_text)
            end = start + len(trimmed_text)

        return cls(src_index=src_index, src_length=src_length, src_breaks=src_breaks, char_range=(start, end))

    @classmethod
    def from_enumerated_paragraphs(cls, paragraphs: Iterator[tuple[int, str]]) -> Iterator['ParagraphSpan']:
        for paragraph_index, paragraph_text in paragraphs:
            yield cls.from_single_paragraph(paragraph_index, paragraph_text)
    
    def splititer(self, src_text: str, splitter: SplitPattern) -> Iterator[tuple['ParagraphSpan', 'ParagraphSpan']]:
        """
        ### Summary
        Return all potential split pairs created from applying a given split pattern to this row metadata.
        """
        matches = [match for match in splitter.pattern.finditer(src_text) if self._range_includes(self.char_range, match.span())]
        for match in matches:
            # Define the border of the split to be the start and end of the pattern match
            split_start, split_end = match.span()

            if any(match.groups()):
                if (SplitBehavior.INCLUDE_LEFT in splitter.behavior):
                    split_start = match.end(1)
                if (SplitBehavior.INCLUDE_RIGHT in splitter.behavior):
                    split_end = match.start(-1)

            left = ParagraphSpan(src_index=self.src_index, src_length=self.src_length, 
                                 src_breaks=self.src_breaks, char_range=(self.char_range[0], split_start))
            right = ParagraphSpan(src_index=self.src_index, src_length=self.src_length, 
                                  src_breaks=self.src_breaks, char_range=(split_end, self.char_range[1]))
            yield left, right
        
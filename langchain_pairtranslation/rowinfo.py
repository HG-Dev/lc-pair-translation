from enum import Enum
import re
from typing import Iterator
from pydantic import BaseModel, Field, PositiveInt, field_validator
from functools import total_ordering

from langchain_pairtranslation.config import SplitBehavior, SplitPattern
from .utils.unsigned_int import UnsignedInt

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
    
class RowMetadata(BaseModel):
    """
    ### Summary
    Metadata defining a portion of a row in a document.
    Row index and row length cannot be changed after initialization.
    ### Attributes
    1. row_index : PositiveInt recording the row index in the original document.
    2. row_length : PositiveInt describing the length of the row.
    3. col_range : UnsignedInt tuple describing the row content range from to [0] to [1] exclusive.
    """
    row_index: UnsignedInt = Field(frozen=True)
    row_length: UnsignedInt = Field(frozen=True)
    col_range: tuple[UnsignedInt, UnsignedInt] = Field(default_factory=lambda data: (0, data['row_length']))

    @field_validator('col_range')
    def check_col_range(cls, rng: tuple[UnsignedInt, UnsignedInt]):
        if rng[0] > rng[1]: raise ValueError('The first element must be less than or equal to the second element')
        return rng

    def __len__(self) -> UnsignedInt:
        return self.length
    
    def __str__(self) -> str:
        return f"Row {self.row_index}[{self.start_col}:{self.end_col}]"

    @property
    def length(self) -> UnsignedInt:
        assert(isinstance(self.col_range, tuple))
        assert(self.end_col >= self.start_col)
        assert(self.end_col - self.start_col >= 0)
        return (self.end_col - self.start_col)
    
    @property
    def start_col(self):
        return self.col_range[0]
    
    @property
    def end_col(self):
        return self.col_range[1]
    
    @property
    def is_row_start(self) -> bool:
        return self.col_range[0] == 0
    
    @property
    def is_row_end(self) -> bool:
        return self.col_range[1] == self.row_length
    
    def eval_adjacency(self, other: 'RowMetadata') -> Adjacency:

        if self.row_index == other.row_index:
            if self.end_col == other.start_col:
                return Adjacency.FORWARD
            if self.start_col == other.end_col:
                return Adjacency.BACKWARD
            if self.col_range == other.col_range:
                return Adjacency.IDENTICAL
            if self._ranges_overlap(self.col_range, other.col_range):
                return Adjacency.OVERLAPPING
        
        # This segment ends a row; precedes the other
        if other.row_index - self.row_index == 1 and self.is_row_end and other.is_row_start:
            return Adjacency.FORWARD
        # This segment starts a row; succeeds the other
        if self.row_index - other.row_index == 1 and self.is_row_start and other.is_row_end:
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
            assert(len(src_row) == self.row_length)
        except AssertionError:
            print(f"Row length mismatch: {len(src_row)} != {self.row_length}  row text: {src_row}")
            raise
        return src_row[self.start_col : self.end_col]
    
    @classmethod
    def from_enumerated_rows(cls, rows: Iterator[tuple[int, str]]) -> Iterator['RowMetadata']:
        for row_index, row in rows:
            row_length = len(row)
            yield cls(row_index=row_index, row_length=row_length, col_range=(0, row_length))
    
    def splititer(self, row_src: str, splitter: SplitPattern) -> Iterator[tuple['RowMetadata', 'RowMetadata']]:
        """
        ### Summary
        Return all potential split pairs created from applying a given split pattern to this row metadata.
        """
        matches = [match for match in splitter.pattern.finditer(row_src) if self._range_includes(self.col_range, match.span())]
        for match in matches:
            # Define the border of the split to be the start and end of the pattern match
            split_start, split_end = match.span()

            if any(match.groups()):
                if (SplitBehavior.INCLUDE_LEFT in splitter.behavior):
                    split_start = match.end(1)
                if (SplitBehavior.INCLUDE_RIGHT in splitter.behavior):
                    split_end = match.start(-1)

            left = RowMetadata(row_index=self.row_index, row_length=self.row_length, col_range=(self.col_range[0], split_start))
            right = RowMetadata(row_index=self.row_index, row_length=self.row_length, col_range=(split_end, self.col_range[1]))
            yield left, right
        

        

        
    #     start, end = match.span()
    #     left = RowMetadata(row_index=self.row_index, col_range=(self.col_start, start))
    #     right = RowMetadata(row_index=self.row_index, col_range=(end, self.col_end))
    #     return left, right
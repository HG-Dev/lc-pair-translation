from enum import Enum
from typing import Callable, Iterator
from pydantic import BaseModel, PositiveInt, Field

from langchain_pairtranslation.config import SplitPattern
from langchain_pairtranslation.rowinfo import Adjacency, RowMetadata
from langchain_pairtranslation.translation_state import TranslationState

from logging import getLogger
LOG = getLogger('app')

class DocumentChunk(BaseModel):
    """Document Chunks are [symantically] cohesive portions of a document sent to an LLM to be translated.

    Chunks can be any length, depending on what's used to break the document into chunks.
    This implies a need to direct translation services to generate output one portion at a time for each individual chunk.
    """
    row_metadata: list[RowMetadata] = Field(
        description="A contiguous series of row metadata detailing rows in the source document.",
        frozen=True
    )
    state: TranslationState = Field(
        description="Whether this chunk is translated, and if so, by who.",
        default=TranslationState.UNTRANSLATED
    )
    warnings: list[str] = Field(
        description="A list of warnings generated during the chunking or translation processes.",
        default=[]
    )

    def to_text(self, row_getter: Callable[[int], str]) -> str:
        """ Get the text of all rows in the chunk from the associated document. """
        rows = []
        for metadata in self.row_metadata:
            rows.append(row_getter(metadata.row_index)[metadata.start_col:metadata.end_col])
        
        return "\n".join(rows)
    
    def to_rows(self, row_getter: Callable[[int], str]) -> Iterator[tuple[RowMetadata, str]]:
        """ Get the text from each row in the chunk from the associated document, as well as their metadata. """
        for metadata in self.row_metadata:
            yield metadata, row_getter(metadata.row_index)[metadata.start_col:metadata.end_col]

    @property
    def start(self) -> RowMetadata:
        return self.row_metadata[0]
    
    @property
    def end(self) -> RowMetadata:
        return self.row_metadata[-1]
    
    def __str__(self) -> str:
        return f"DocumentChunk: {str(self.start)} to {str(self.end)}"
    
    def __iter__(self) -> Iterator[RowMetadata]:
        return iter(self.row_metadata)
    
    def eval_adjacency(self, other: 'DocumentChunk') -> Adjacency:
        """ Determine if this chunk is adjacent to another chunk. """
        if forward_adjacency := self.end.eval_adjacency(other.start):
            return forward_adjacency
        elif backward_adjacency := self.start.eval_adjacency(other.end):
            return backward_adjacency
        
        return Adjacency.NONE

    def __len__(self) -> int:
        lengths = [row.length for row in self.row_metadata]
        assert(all([length >= 0 for length in lengths]))
        return sum(lengths)

    @classmethod
    def from_full_src_row(cls, index: int, text: str) -> 'DocumentChunk':
        """ Create a DocumentChunk from a list of rows. """
        return cls(row_metadata=[RowMetadata(row_index=index, row_length=len(text))], state=TranslationState.UNTRANSLATED)


class BaseDocumentChunks(BaseModel):
    """
    ### Summary
    A collection of translateable document chunks.
    """
    file_path: str | None = Field(
        description="The file path document from which the chunks were drawn. Empty if the chunks were generated from strings.",
        frozen=True,
        default=None
    )
    collection: list[DocumentChunk] = Field(
        description="The internal collection of document chunks."
    )

    def __iter__(self) -> Iterator[DocumentChunk]:
        return iter(self.collection)
    
    def __getitem__(self, index: int) -> DocumentChunk:
        return self.collection[index]
    
    def __len__(self) -> int:    
        return len(self.collection)

    def merge_pass(self, max_length: PositiveInt) -> None:
        """ Merge adjacent chunks into a single chunk if they are within the specified length constraints. """
        
        if (not self.collection or len(self.collection) <= 1):
            return
        
        merged_chunks = []
        current_chunk = self.collection[0]
        for chunk in self.collection[1:]:
            if current_chunk.eval_adjacency(chunk) == Adjacency.FORWARD and len(current_chunk) + len(chunk) <= max_length:
                current_chunk.row_metadata.extend(chunk.row_metadata)
            else:
                merged_chunks.append(current_chunk)
                current_chunk = chunk
            
        merged_chunks.append(current_chunk)
        self.collection = merged_chunks

    def split_pass(self, row_getter: Callable[[int], str], max_length: PositiveInt, splitters: list[SplitPattern]) -> None:
        """ Split chunks into smaller chunks if they exceed the specified length constraint. """
        if not self.collection:
            return
        
        self.collection = [split_chunk for chunk in self for split_chunk in self._split_chunk(chunk, row_getter, max_length, splitters)]

    @staticmethod
    def _split_chunk(chunk: DocumentChunk, row_getter: Callable[[int], str], max_length: PositiveInt, splitters: list[SplitPattern]) -> list[DocumentChunk]:
        """ Split a single chunk into smaller chunks if it exceeds the specified length constraint. """
        if len(chunk) <= max_length:
            return [chunk]
        
        assert(row_getter is not None)
        assert(splitters is not None)
        chunk_rows = chunk.row_metadata
        split_chunks = []
        next_chunk_metadata = []
        next_chunk_length = 0
        LOG.debug("Starting split of chunk with %d rows", len(chunk.row_metadata))
        while chunk_rows: # Digest all rows in chunk
            
            row_metadata = chunk_rows.pop(0)
            LOG.debug("Processing row %s (%s)", str(row_metadata), row_metadata.to_text(row_getter(row_metadata.row_index)))

            # Remerge rows into the next chunk while max length has not been exceeded
            if next_chunk_length + row_metadata.length <= max_length:
                LOG.debug("Row #%d placed in split chunk #%d", row_metadata.row_index, len(split_chunks))
                next_chunk_metadata.append(row_metadata)
                next_chunk_length += row_metadata.length
                continue

            # max length has been exceeded; find the first splitter that can split row text
            row_text = row_getter(row_metadata.row_index)
            LOG.debug("Splitting row")
            for splitter in splitters:
                LOG.debug("Trying splitter <%s>", splitter.name)
                # Find all potential splits that do not exceed maximum length for this chunk
                potential_splits = [pair for pair in row_metadata.splititer(row_text, splitter) 
                                    if pair[0].end_col - row_metadata.start_col + next_chunk_length <= max_length]
                if not potential_splits:
                    continue
                
                LOG.debug("Splitter <%s> found %d potential splits", splitter.name, len(potential_splits))
                lhs, rhs = potential_splits[-1]
                next_chunk_metadata.append(lhs) # Finish off the current chunk
                LOG.debug("LHS = %s", lhs.to_text(row_text))
                split_chunks.append(DocumentChunk(row_metadata=next_chunk_metadata))

                next_chunk_metadata = [] # Start a new chunk
                LOG.debug("RHS = %s", rhs.to_text(row_text))
                next_chunk_length = 0
                chunk_rows.insert(0, rhs) # Reinsert the row that was split to confirm property length

                row_metadata = None
                break
            
            # If splitting failed, create a new chunk with the current row anyway
            # and add a warning to the chunk
            if row_metadata:
                LOG.warning("Max length (%d) exceeded on unsplittable row section %s", max_length, str(row_metadata))
                split_chunks.append(DocumentChunk(row_metadata=[row_metadata], warnings=[f"Max length ({max_length}) exceeded"]))

        if next_chunk_metadata:
            split_chunks.append(DocumentChunk(row_metadata=next_chunk_metadata))

        LOG.debug("Chunk was split into %d smaller chunks", len(split_chunks))
        return split_chunks
        
    @classmethod
    def from_strings(cls, rows: list[str]) -> 'BaseDocumentChunks':
        """ Create a BaseDocumentChunks object from a list of strings. """
        chunks = [DocumentChunk.from_full_src_row(row_index, row) for row_index, row in enumerate(rows)]
        return cls(collection=chunks)

    def to_row_overrides_iter(self, row_getter: Callable[[int], str]) -> Iterator[tuple[RowMetadata, str]]:
        """ Get the text of all rows in the chunk from the associated document. """
        for chunk in self.collection:
            for row in chunk.to_rows(row_getter):
                yield row

    def to_row_exports_iter(self, row_getter: Callable[[int], str], total_rows: int) -> Iterator[str]:
        """ Get the text of all rows in the chunk from the associated document. """
        override_dict: dict[int, list[RowMetadata]] = {}
        for chunk in self.collection:
            for row_overrides in chunk:
                overrides = override_dict.get(row_overrides.row_index, [])
                overrides.append(row_overrides)
                override_dict[row_overrides.row_index] = overrides

        # For each row in the document, return each row with overrides applied
        for row_index in range(total_rows):
            row_overrides = override_dict.get(row_index, [])
            src_row_text = row_getter(row_index)
            final_row_text = ""
            insertion_point = 0

            for override in row_overrides:
                # Copy text from the source row up to the start of the override
                if override.start_col > insertion_point:
                    final_row_text += src_row_text[insertion_point:override.start_col]

                # Copy the override text
                final_row_text += override.to_text(src_row_text)

                # Update the insertion point
                insertion_point = override.end_col

            if insertion_point < len(src_row_text):
                final_row_text += src_row_text[insertion_point:]
            yield final_row_text
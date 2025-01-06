from enum import Enum
from typing import Callable, Iterator
from pydantic import BaseModel, PositiveInt, Field

from langchain_pairtranslation.config import SplitPattern
from langchain_pairtranslation.rowinfo import Adjacency, ParagraphSpan
from langchain_pairtranslation.translation_state import TranslationState
from re import compile, Pattern

from logging import getLogger
LOG = getLogger('app')

class DocumentChunk(BaseModel):
    """Document Chunks are [symantically] cohesive portions of a document sent to an LLM to be translated.

    Chunks can be any length, depending on what's used to break the document into chunks.
    This implies a need to direct translation services to generate output one portion at a time for each individual chunk.
    """
    paragraph_metadata: list[ParagraphSpan] = Field(
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
        for metadata in self.paragraph_metadata:
            rows.append(row_getter(metadata.src_index)[metadata.start:metadata.end])
        
        return "\n".join(rows)
    
    def to_paragraphs(self, row_getter: Callable[[int], str]) -> Iterator[tuple[ParagraphSpan, str]]:
        """ Get the text from each row in the chunk from the associated document, as well as their metadata. """
        for metadata in self.paragraph_metadata:
            yield metadata, row_getter(metadata.src_index)[metadata.start:metadata.end]

    @property
    def start(self) -> ParagraphSpan:
        return self.paragraph_metadata[0]
    
    @property
    def end(self) -> ParagraphSpan:
        return self.paragraph_metadata[-1]
    
    def __str__(self) -> str:
        return f"DocumentChunk: {str(self.start)} to {str(self.end)}"
    
    def __iter__(self) -> Iterator[ParagraphSpan]:
        return iter(self.paragraph_metadata)
    
    def eval_adjacency(self, other: 'DocumentChunk') -> Adjacency:
        """ Determine if this chunk is adjacent to another chunk. """
        if forward_adjacency := self.end.eval_adjacency(other.start):
            return forward_adjacency
        elif backward_adjacency := self.start.eval_adjacency(other.end):
            return backward_adjacency
        
        return Adjacency.NONE

    def __len__(self) -> int:
        lengths = [row.length for row in self.paragraph_metadata]
        assert(all([length >= 0 for length in lengths]))
        return sum(lengths)

    @classmethod
    def from_single_paragraph(cls, index: int, text: str) -> 'DocumentChunk':
        """ Create a DocumentChunk from a single row. """
        if (text.strip() == ""):
            raise ValueError("Cannot create a DocumentChunk from an empty row.")
        
        return cls(paragraph_metadata=[ParagraphSpan.from_single_paragraph(index, text)], state=TranslationState.UNTRANSLATED)


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
                current_chunk.paragraph_metadata.extend(chunk.paragraph_metadata)
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
        chunk_rows = chunk.paragraph_metadata
        split_chunks = []
        next_chunk_metadata = []
        next_chunk_length = 0
        LOG.debug("Starting split of chunk with %d rows", len(chunk.paragraph_metadata))
        while chunk_rows: # Digest all rows in chunk
            
            paragraph_metadata = chunk_rows.pop(0)
            LOG.debug("Processing row %s (%s)", str(paragraph_metadata), paragraph_metadata.to_text(row_getter(paragraph_metadata.src_index)))

            # Remerge rows into the next chunk while max length has not been exceeded
            if next_chunk_length + paragraph_metadata.length <= max_length:
                LOG.debug("Row #%d placed in split chunk #%d", paragraph_metadata.src_index, len(split_chunks))
                next_chunk_metadata.append(paragraph_metadata)
                next_chunk_length += paragraph_metadata.length
                continue

            # max length has been exceeded; find the first splitter that can split row text
            row_text = row_getter(paragraph_metadata.src_index)
            LOG.debug("Splitting row")
            for splitter in splitters:
                LOG.debug("Trying splitter <%s>", splitter.name)
                # Find all potential splits that do not exceed maximum length for this chunk
                potential_splits = [pair for pair in paragraph_metadata.splititer(row_text, splitter) 
                                    if pair[0].end - paragraph_metadata.start + next_chunk_length <= max_length]
                if not potential_splits:
                    continue
                
                LOG.debug("Splitter <%s> found %d potential splits", splitter.name, len(potential_splits))
                lhs, rhs = potential_splits[-1]
                next_chunk_metadata.append(lhs) # Finish off the current chunk
                LOG.debug("LHS = %s", lhs.to_text(row_text))
                split_chunks.append(DocumentChunk(paragraph_metadata=next_chunk_metadata))

                next_chunk_metadata = [] # Start a new chunk
                LOG.debug("RHS = %s", rhs.to_text(row_text))
                next_chunk_length = 0
                chunk_rows.insert(0, rhs) # Reinsert the row that was split to confirm property length

                paragraph_metadata = None
                break
            
            # If splitting failed, create a new chunk with the current row anyway
            # and add a warning to the chunk
            if paragraph_metadata:
                LOG.warning("Max length (%d) exceeded on unsplittable row section %s", max_length, str(paragraph_metadata))
                split_chunks.append(DocumentChunk(paragraph_metadata=[paragraph_metadata], warnings=[f"Max length ({max_length}) exceeded"]))

        if next_chunk_metadata:
            split_chunks.append(DocumentChunk(paragraph_metadata=next_chunk_metadata))

        LOG.debug("Chunk was split into %d smaller chunks", len(split_chunks))
        return split_chunks
        
    @classmethod
    def from_paragraphs(cls, paragraphs: list[str]) -> 'BaseDocumentChunks':
        """ Create a BaseDocumentChunks object from a list of strings. """
        chunks = [DocumentChunk.from_single_paragraph(pindex, ptext) for pindex, ptext in enumerate(paragraphs) if ptext.strip() != ""]
        return cls(collection=chunks)

    def to_paragraph_overrides_iter(self, src_getter: Callable[[int], str]) -> Iterator[tuple[ParagraphSpan, str]]:
        """ Get the text of all rows in the chunk from the associated document. """
        for chunk in self.collection:
            for row in chunk.to_paragraphs(src_getter):
                yield row

    def to_paragraph_exports_iter(self, src_getter: Callable[[int], str], total_rows: int) -> Iterator[str]:
        """ Get the text of all rows in the chunk from the associated document. """
        override_dict: dict[int, list[ParagraphSpan]] = {}
        for chunk in self.collection:
            for paragraph_overrides in chunk:
                overrides = override_dict.get(paragraph_overrides.src_index, [])
                overrides.append(paragraph_overrides)
                override_dict[paragraph_overrides.src_index] = overrides

        # For each row in the document, return each row with overrides applied
        for pindex in range(total_rows):
            paragraph_overrides = override_dict.get(pindex, [])
            src_text = src_getter(pindex)
            final_paragraph_text = ""
            insertion_point = 0

            for override in paragraph_overrides:
                # Copy text from the source row up to the start of the override
                if override.start > insertion_point:
                    final_paragraph_text += src_text[insertion_point:override.start]

                # Copy the override text
                final_paragraph_text += override.to_text(src_text)

                # Update the insertion point
                insertion_point = override.end

            if insertion_point < len(src_text):
                final_paragraph_text += src_text[insertion_point:]
            yield final_paragraph_text
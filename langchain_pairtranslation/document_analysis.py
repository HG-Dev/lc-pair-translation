from typing import Annotated, Dict, Iterator, List, Callable, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass
import annotated_types
from frozenlist import FrozenList
from functools import cached_property
from logging import getLogger
from pydantic import BaseModel, RootModel
import re

UnsignedInt = Annotated[int, annotated_types.Ge(0)]

import langchain_pairtranslation.utils.string_extensions as string
logger = getLogger("__main__")

class DocumentTerm(BaseModel):
    """
    ### Summary
    Document Terms are source-to-translation mappings with added description for context details.
    ### Attributes
        1. source : str
        2. translations : List{str}
        3. description : Optional{str}
    """
    source: str
    translations: List[str]
    description: Optional[str]

    def __str__(self):
        if self.description:
            return f"{self.source} = {', '.join(self.translations)}\n\t- {self.description}"
        return f"{self.source} = {', '.join(self.translations)}"

class DocumentTerms(RootModel):
    root: List[DocumentTerm]

    def __iter__(self):
        return iter(self.root)
    
    def __getitem__(self, idx):
        return self.root[idx]
    
    def __str__(self):
        return '\n\n'.join([str(entry) for entry in self.root])
    
    def to_kv_dict(self) -> Dict[str, Tuple[str, ...]]:
        """
        ### Summary
        Converts one-to-many term-to-translation items into a dictionary.
        ### Returns
        A dictionary of term source keys to translation tuples.
        """
        return dict({term.source : tuple(term.translations) for term in self.root})

    def to_vk_dict(self) -> Dict[str, Tuple[str, ...]]:
        """
        ### Summary
        Converts one-to-many term-to-translation items into a flipped dictionary,
        where each translation points to one or more source terms.
        Useful for confirming the validity of translations.
        ### Returns
        A dictionary of term translation keys to source tuples.
        """
        output: Dict[str, Set[str]] = {}
        for term in self.root:
            for translation in term.translations:
                kset = output.get(translation, set())
                kset.add(term.source)
        return dict({v:tuple(k) for (v, k) in output.items()})
    
class DocumentFormattingRule(BaseModel):
    """
    ### Summary
    Modifications applied or injected into translated text
    to produce better localized output documents.   
    """
    description: str
    examples: List[Tuple[str]]





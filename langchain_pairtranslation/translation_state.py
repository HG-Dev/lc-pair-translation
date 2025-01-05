from enum import Enum

from langchain_pairtranslation.utils.enum_extensions import enum_ordering   

@enum_ordering
class TranslationState(Enum):
    UNTRANSLATED = 0
    LLM_TRANSLATED = 10
    USER_TRANSLATED = 20
    USER_EDITED = 30
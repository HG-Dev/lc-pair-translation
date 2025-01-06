from enum import Enum, Flag, auto
from functools import cached_property
import re
from pydantic import BaseModel, PositiveInt
from os.path import exists

class SplitBehavior(Flag):
    """
    ### Description
    Enum for the behavior of a split pattern, specifically whether or not the matched pattern
    should be included in the output, and if so, on which side of the split.
        * INCLUDE_LEFT:  The matched pattern is included in the left chunk. 
        * INCLUDE_RIGHT: The matched pattern is included in the right chunk.
        * EXCLUDE:       The matched pattern is excluded from chunks.
    """
    EXCLUDE = auto()
    INCLUDE_LEFT = auto()
    INCLUDE_RIGHT = auto()
    INCLUDE_BOTH = INCLUDE_LEFT | INCLUDE_RIGHT

class ReplaceBehavior(Enum):
    """
    ### Description
    Enum for the behavior of a replacement pattern.
        * IMMEDIATE: The replacement pattern is applied immediately.
                     The user and LLM will see the same text.
        * ON_SUBMIT: The replacement pattern is applied when the chunk is submitted for translation.
                     Only the LLM will see the post-processed text. This is useful for trimming text that is less useful to the LLM than the user.
        * ON_EXPORT: The replacement pattern is applied when the translation is exported to a new document.
                     This is useful for performing replacements on the final document that are not necessary for the LLM or user to see.
    """
    IMMEDIATE = "immediate"
    ON_SUBMIT = "on_submit"
    ON_EXPORT = "on_export"

CAPTURE_LEFT = re.compile(r'^\(.*?\)')
CAPTURE_RIGHT = re.compile(r'.*?\(.*?\)$')

class SplitPattern(BaseModel):
    """
    ### Description
    A regex pattern for splitting chunks into smaller chunks.
    Capture groups flush with the start of the pattern will be included in the left chunk,
        while capture groups flush with the end of the pattern will be included in the right chunk.
    ### Attributes
    1. name : str
            * The name of the pattern.
    2. pattern : str
            * The regex pattern.
    """
    name: str
    pattern_src: str

    @cached_property
    def pattern(self) -> re.Pattern:
        return re.compile(self.pattern_src)
    
    # TODO Consider determining behavior from returned matches -- this would allow for more complex patterns
    @cached_property
    def behavior(self):
        """
        Capture groups in split patterns can be used to determine whether
        portions of the matched text should be included in the left or right chunks.
        """
        # Check for capture groups at the start and end of the pattern
        include_left = bool(CAPTURE_LEFT.match(self.pattern_src))
        include_right = bool(CAPTURE_RIGHT.match(self.pattern_src))
        
        if include_left and include_right:
                return SplitBehavior.INCLUDE_BOTH
        elif include_left:
                return SplitBehavior.INCLUDE_LEFT
        elif include_right:
                return SplitBehavior.INCLUDE_RIGHT
        else:
                return SplitBehavior.EXCLUDE
            

class ReplacePattern(BaseModel):
    """
    ### Description
    A regex pattern for replacing text within a chunk.
    This could be used to remove or preformat a chunk before it is sent to the translator.
    ### Attributes
    1. name : str
            * The name of the pattern.
    2. pattern : str
            * The regex pattern.
    3. replacement : str | None
            * The replacement string. If this is not supplied, the pattern match will be removed.
    4. behavior : ReplaceBehavior
            * The behavior of the replacement pattern.
    """
    name: str
    pattern_src: str
    replacement: str | None
    behavior: ReplaceBehavior = ReplaceBehavior.IMMEDIATE

    @cached_property
    def pattern(self):
        return re.compile(self.pattern_src)

class ChunkingSettings(BaseModel):
    """
    ### Description
    Settings for chunking text into segments.
    ### Attributes
    1. int_MinLength : int
            * The minimum length of a chunk.
    2. int_MaxLength : int
            * The maximum length of a chunk. This should be constrained to prevent LLMs from generating too much text at once.
    3. split_patterns : list[SplitPattern]
            * A list of regex patterns for splitting text into segments. Priority is given to patterns earlier in the list.
    """
    min_length: PositiveInt = 64
    max_length: PositiveInt = 512
    split_patterns: list[SplitPattern] = [
        # PRIMARY SPLIT PATTERNS - Guaranteed to be semantically meaningful.
        SplitPattern(name="Blank Space", pattern_src=r'^\s*$'),
        SplitPattern(name="Manuscript Scene Header Maru", pattern_src=r'^(〇)'),
        SplitPattern(name="Manuscript Subscene Break", pattern_src=r'^\s*×\s+×\s+×\s*$'),
        # SECONDARY SPLIT PATTERNS
        SplitPattern(name="End of sentence (en/jp)", pattern_src=r'([.!?。！？…]+)[^A-z0-9."]'),
    ]

class UserSettings(BaseModel):
    """
    ### Description
    User settings for the application.
    ### Attributes
    1. source_language : str
            * The source language of the document.
    2. target_language : str
            * The target language of the document.
    3. window_size : str
            * The size of the main window.
    """
    known_languages: list[str] = ["Japanese", "English"]
    source_language: str = "Japanese"
    target_language: str = "English"
    window_size: str = '1280x960'

class Config(BaseModel):
    """
    ### Description
    Root configuration model for the application.
    """
    chunking: ChunkingSettings = ChunkingSettings()
    user: UserSettings = UserSettings()
    system_prompt_path: str = "config/prompts/translator_system_prompt.json"

    @staticmethod
    def _create_default(path: str) -> 'Config':
        default = Config()
        default.save(path)
        return default

    @staticmethod
    def load(path: str) -> 'Config':
        if not exists(path):
            return Config._create_default(path)
        
        with open(path, 'r') as file:
            json = file.read()
            if (json.strip() == ""):
                return Config._create_default(path)
            return Config.model_validate_json(json)
        
    def save(self, path: str):
        with open(path, 'w') as file:
            file.write(self.model_dump_json())
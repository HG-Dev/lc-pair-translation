''' Compile-time configuration data IO '''
import json
from typing import Optional, Dict, Any
from os import path, mkdir
from re import sub, compile, Pattern
from functools import cached_property
from configparser import ConfigParser, ParsingError
from warnings import deprecated
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, AIMessagePromptTemplate
from logging import getLogger, warning

from langchain_pairtranslation.document_analysis import DocumentTerms

DEFAULT_SOURCE_TARGET = ("Japanese", "English")

CHUNK_SETTINGS_H = "Chunk Settings"
CHUNK_PATTERNS_H = "Regex Chunk Patterns"
FILEPATHS_H = "General Filepaths"
USER_SETTINGS_TEMPLATE_H = "User Settings > Template Parameters"

def create_default_config_dict() -> Dict[str, Dict[str, Any]]:
    return {
            CHUNK_SETTINGS_H : {
                'int_MinLength' : 24
            },
            CHUNK_PATTERNS_H : {
                'Empty_Line'  : r"^\s*$",
                'Maru'        : r"^〇",
                'Triple_X'    : r"×\s+×\s+×"
            },
            FILEPATHS_H : {
                'Logging'               : "",#"__logs__/debug.log",
                'TranslatorSystemPrompt': "",#"config/prompts/translator_system_prompt.txt"
            },
            USER_SETTINGS_TEMPLATE_H : {
                'SourceLanguage': DEFAULT_SOURCE_TARGET[0],
                'TargetLanguage': DEFAULT_SOURCE_TARGET[1]
            }
        }

logger = getLogger(__name__)

class LoadConfigError(Exception):
    ''' Raised when you fail to load config info. '''
    pass

class Config:
    """
    ### Description
    Regenerative .ini config file interpretation
    ### Parameters
    1. ini_filepath : str
            * The filepath for the configuration file. If you do not supply this, 
              default settings will be used, and any changes made will be lost.
    """
    def __init__(self, ini_filepath: Optional[str] = None):

        self.ini_filepath = ini_filepath

        # Attempt to load config file from given filepath
        self.config = ConfigParser(allow_no_value=True)
        if self.ini_filepath:
            file_ext = path.splitext(self.ini_filepath)[-1]
            if not file_ext:
                logger.warning("For clarity's sake, ensure the specified .ini file name ({}) includes its file extension.".format(self.ini_filepath))
                self.ini_filepath += ".ini"
            elif file_ext != ".ini":
                raise LoadConfigError("TweetFeeder config file should be of .ini type.")
            if path.exists(self.ini_filepath):
                try:
                    assert path.isfile(self.ini_filepath)
                    self.config.read(self.ini_filepath)          
                except (AssertionError, ParsingError) as e:
                    raise LoadConfigError("Error parsing config ({}).".format(self.ini_filepath))
            else:
                logger.warning("No config file at given filepath ({}). It will be created.".format(self.ini_filepath))
        
        # Internal dictionary that represents the config file's sections, options, and default values
        # All string values can be called safely from this dictionary
        self._config_dict = create_default_config_dict()
        assert(FILEPATHS_H in self._config_dict)

        # Where existing settings are found, overwrite items in _config_dict
        self._load_settings_ini()

        # Check filepaths before proceeding
        path_errors = self.verify_paths()
        if path_errors:
            raise LoadConfigError("The following paths failed verification: " + str(path_errors))

        # Save config file, adding missing options or sections
        if ini_filepath:
            self._save_settings_ini()

    def _load_settings_ini(self):
        # Iterate over internal dictionary to both update self.values and generate config file
        for section, option_dict in self._config_dict.items():
            # Ensure sections
            if not self.config.has_section(section):
                self.config.add_section(section)
            # Ensure options or read options
            for option, value in option_dict.items():
                if not self.config.has_option(section, option):
                    self.config.set(section, option, str(value))
                else:
                    match option.split('_')[0]:
                        case 'int':     self._config_dict[section][option] = self.config.getint(section, option)
                        case 'float':   self._config_dict[section][option] = self.config.getfloat(section, option)
                        case 'bool':    self._config_dict[section][option] = self.config.getboolean(section, option)
                        case _:         self._config_dict[section][option] = self.config.get(section, option)

    def _save_settings_ini(self):
        if not self.ini_filepath:
            logger.warning("No configuration filename was given. Changes to settings will not be saved.")
            return
        with open(self.ini_filepath, 'w') as configfile:
            self.config.write(configfile)

    @property
    def log_filepath(self):
        ''' Return filepath to the log. '''
        return self._config_dict[FILEPATHS_H]['log']

    @property
    def min_chunk_length(self):
        ''' The minimum number of characters required to exist in the chunk buffer before a chunk is registered. '''
        value = self._config_dict[CHUNK_SETTINGS_H]['int_MinLength']
        assert(isinstance(value, int))
        return value
    
    @cached_property
    def translator_base_system_prompt(self) -> SystemMessagePromptTemplate:
        return SystemMessagePromptTemplate.from_template_file(
            template_file=self._config_dict[FILEPATHS_H]['TranslatorSystemPrompt'],
            input_variables=list(self._config_dict[USER_SETTINGS_TEMPLATE_H].keys()))
    
    @property
    @deprecated("Make terms set / get during runtime not config")
    def terms(self) -> DocumentTerms:
        with open('config/terms.json', 'r') as file:
            return DocumentTerms.model_validate_json(file.read())

    @terms.setter
    def terms(self, value: DocumentTerms):
        with open('config/terms.json', 'w') as file:
            file.write(value.model_dump_json())

    @property
    def translator_format_kwargs(self) -> Dict[str, str]:
        return self._config_dict[USER_SETTINGS_TEMPLATE_H]

    @property
    def current_chunk_divider_regex(self) -> Pattern:
        ''' The unified regex pattern that can be searched for to find a chunk division. '''
        return compile('(' + '|'.join([pattern for (key, pattern) in self._config_dict[CHUNK_PATTERNS_H].items() if not key.startswith('#')]) + ')')
    
    @property
    def source_language(self) -> str:
        ''' Document source language '''
        value = self._config_dict[USER_SETTINGS_TEMPLATE_H]['SourceLanguage']
        return value
    
    @source_language.setter
    def source_language(self, value: str):
        ''' Set and save document source language '''
        self._config_dict[USER_SETTINGS_TEMPLATE_H]['SourceLanguage'] = value
        self._save_settings_ini()

    @property
    def target_language(self) -> str:
        ''' Document target language '''
        value = self._config_dict[USER_SETTINGS_TEMPLATE_H]["TargetLanguage"]
        return value
    
    @target_language.setter
    def target_language(self, value: str):
        ''' Set and save the document target language '''
        self._config_dict[USER_SETTINGS_TEMPLATE_H]['TargetLanguage'] = value
        self._save_settings_ini()

    def verify_paths(self):
        ''' Ensures that the paths given for feed/stats files can be used. '''
        problems = set()
        if FILEPATHS_H not in self._config_dict:
            return f"{FILEPATHS_H}: {KeyError("File paths category not found in config dict")}"
        for name, filepath in self._config_dict[FILEPATHS_H].items():
            if filepath and filepath.strip() != '':
                # If the file has yet to be created, ensure it can be written to
                if not path.exists(path.dirname(filepath)):
                    try:
                        mkdir(filepath)
                    except OSError as e:                  
                        problems.add(path.dirname(filepath) + ": " + str(e))
            else:
                problems.add(f"{name}: {KeyError("No filepath given")}")
        return problems
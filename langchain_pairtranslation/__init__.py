import logging
from typing import Union, Tuple, Optional, Callable
from tkinter.constants import *
from customtkinter.windows.widgets.theme import ThemeManager
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, AIMessagePromptTemplate
import customtkinter as ctk
import logging
import asyncio
from langchain_pairtranslation.customtkinter_extensions import *
from langchain_pairtranslation.document_analysis import *
from langchain_pairtranslation.llms import BaseLLMProvider
import langchain_pairtranslation.utils.string_extensions as string
#from langchain_pairtranslation._internal import MyLLMProvider
from langchain_pairtranslation.chunking.base import DocumentChunk
from langchain_pairtranslation.chunking.docx import DocxChunks
from langchain_pairtranslation.config_old import ConfigOld

config: ConfigOld = ConfigOld(None)

def load_config(ini_filepath: str):
    config = ConfigOld(ini_filepath)

# def get_logger() -> logging.Logger: TODO: Figure out why this causes circular import error
#     return logging.getLogger("app")

def run(ini_filepath: str | None):
    if ini_filepath:
        load_config(ini_filepath)

    root = ctk.CTk()
    root.title("LangChain Paired Translation")
    root.geometry(config.window_size)
    #root.iconbitmap('resoures/something.ico')
    ctk.FontManager.load_font('resources/fonts/RobotoMono-Regular.ttf')
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    status_frame = ctk.CTkFrame(root, height=24)
    status_frame.pack(side=BOTTOM, fill=X)

    ctrl_frame = ctk.CTkFrame(root, height=64, bg_color=ThemeManager.theme["CTkScrollableFrame"]["label_fg_color"])
    ctrl_frame.pack(side=TOP, fill=X)

    text_frame = ChunkedTranslationFrame(root, bg_color="black", fg_color="black")
    text_frame.pack(side=TOP, fill=BOTH, expand=TRUE)

    chunks = DocxChunks(doc_path="")

    chunks.split_document()

    for chunk in chunks:
        text_frame.add_chunk(chunk)

    ctrls = TranslationController(ctrl_frame, config, text_frame._chunks)

    root.mainloop()

class TranslationController:
    def __init__(self, master: ctk.CTkFrame, config: ConfigOld, chunks: List[DocumentChunk]):
        master.grid_columnconfigure(0, weight=1)
        master.grid_columnconfigure(1, weight=0)
        master.grid_columnconfigure(2, weight=1)
        master.grid_rowconfigure(0, weight=1, minsize=64-10)
        master.grid_rowconfigure(1, weight=1, minsize=10)
        self._config = config
        self.main_button_txt = ctk.StringVar(master, value="Translate Next Chunk")
        self.main_button = ctk.CTkButton(master, width=256, height=32)
        self.main_button.configure(command=self.start_translation, textvariable=self.main_button_txt)
        self.progressbar = ctk.CTkProgressBar(master, mode="indeterminate")
        self.progressbar_placeholder = ctk.CTkFrame(master, bg_color="transparent", fg_color="transparent", height=self.progressbar._current_height)
        self.main_button.grid(column=1, row=0, pady=2, sticky=S)
        self.progressbar_placeholder.grid(column=1, row=1, pady=2, sticky="SWE")
        self._chunks = chunks

    def _show_progressbar(self, value: bool):
        if value:
            self.progressbar_placeholder.grid_forget()
            self.progressbar.grid(column=1, row=1, pady=2, sticky="SWE")
            self.progressbar.start()
        else:
            self.progressbar.stop()
            self.progressbar.grid_forget()
            self.progressbar_placeholder.grid(column=1, row=1, pady=2, sticky="SWE")

    def start_translation(self, **kwargs):
        self.main_button.configure(state=DISABLED)
        for key, value in kwargs.items():
            print(key, value)
        self._show_progressbar(True)
        # Get next untranslated chunk
        for chunk in self._chunks:
            if chunk.state == DocumentChunk.TranslationState.UNTRANSLATED:
                logger.info("Found untranslated chunk: {}".format(string.truncate_multi(chunk.src_text_substrings, 24, "...").replace('\n', '¶')))
                asyncio.run(self._start_translation_internal(chunk, config))
                
                return
        logger.warning("All chunks are translated!")
        #asyncio.run()

    @staticmethod
    async def _start_translation_internal(chunk: DocumentChunk, config: ConfigOld):
        # Prepare LLM and prompt
        #llm = await MyLLMProvider().create_translator()
        translator_kwargs = config.translator_format_kwargs
        sysprompt = config.translator_base_system_prompt
        # terms = [
        #     DocumentTerm(source="in", translations=["out"], description="DO NOT SAVE THIS"),
        # ]
        #print(string.wrap_with_xml_tag(str(config.terms), "TERMS"))

        sysP = SystemMessagePromptTemplate.from_template("System prompt {test}")
        exHuman = HumanMessagePromptTemplate.from_template("Hello, world!")
        exAI = AIMessagePromptTemplate.from_template("HELLOTE W0RLD!")
        promptTemplate = ChatPromptTemplate.from_messages([sysP, exHuman, exAI])
        print(promptTemplate.format_prompt(test="test successful").to_string())
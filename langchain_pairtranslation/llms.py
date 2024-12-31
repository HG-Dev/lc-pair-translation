from langchain_core.language_models import LLM
from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    @abstractmethod
    async def create_translator(self) -> LLM:
        pass
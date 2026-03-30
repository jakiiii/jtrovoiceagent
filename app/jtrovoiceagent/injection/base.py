from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class InjectionResult:
    text: str
    backend: str
    dry_run: bool


class TextInjector(ABC):
    @abstractmethod
    def inject_text(self, text: str) -> InjectionResult:
        raise NotImplementedError

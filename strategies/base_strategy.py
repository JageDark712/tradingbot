"""
Interfaz base que toda estrategia debe respetar, para que el scorer de
confluencia pueda combinarlas sin conocer los detalles internos de cada una.
"""
from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """
    Toda estrategia debe implementar evaluate(symbol) y devolver un dict con:
        - direction: "alcista" / "bajista" / "sin_senal"
        - strength: float entre 0.0 y 1.0
        - details: dict con información de debug específica de la estrategia
    """

    name: str = "base"

    @abstractmethod
    def evaluate(self, symbol: str) -> dict:
        ...

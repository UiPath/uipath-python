from abc import ABC, abstractmethod


class ClIService(ABC):
    """
    Abstract class implemented by services supported in the CLI commands.
    """
    @abstractmethod
    def _list(self, **kwargs):
        pass

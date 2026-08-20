from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..models import UnifiedNote


class BaseProvider(ABC):
    """Abstract base class for all note providers."""

    name: str = "base"
    display_name: str = "Base Provider"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the remote platform or validate provided credentials/cookies."""
        pass

    @abstractmethod
    def fetch_notes(self) -> List[UnifiedNote]:
        """Fetch all notes from the platform and return normalized UnifiedNote objects."""
        pass

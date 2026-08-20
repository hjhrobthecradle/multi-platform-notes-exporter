from .base import BaseProvider
from .xiaomi import XiaomiNotesProvider
from .oppo import OppoNotesProvider
from .vivo import VivoNotesProvider
from .apple import AppleNotesProvider
from .google import GoogleKeepProvider

PROVIDERS = {
    "xiaomi": XiaomiNotesProvider,
    "oppo": OppoNotesProvider,
    "vivo": VivoNotesProvider,
    "apple": AppleNotesProvider,
    "google": GoogleKeepProvider,
}

__all__ = [
    "BaseProvider",
    "XiaomiNotesProvider",
    "OppoNotesProvider",
    "VivoNotesProvider",
    "AppleNotesProvider",
    "GoogleKeepProvider",
    "PROVIDERS",
]

__version__ = "1.0.0"

from .ecdict import ecdict_translate
from .stardict import open_dict, convert_dict

__all__ = [
    "open_dict",
    "convert_dict",
    "ecdict_translate",
]

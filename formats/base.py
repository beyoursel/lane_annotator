"""Base format interface for lane annotations."""

from abc import ABC, abstractmethod
from typing import List, Tuple

import numpy as np

from models import Lane


class BaseFormat(ABC):
    """Abstract interface for loading and saving lane annotations."""

    def __init__(self, img_root: str):
        self.img_root = img_root

    @abstractmethod
    def load(self, img_path: str) -> Tuple[np.ndarray, List[Lane]]:
        """Load image and its lanes.

        Returns:
            image: BGR image as numpy array.
            lanes: List of Lane objects.
        """
        pass

    @abstractmethod
    def save(self, img_path: str, lanes: List[Lane], out_root: str):
        """Save lanes for a single image to out_root."""
        pass

    @abstractmethod
    def label_exists(self, img_path: str) -> bool:
        """Return True if annotation exists for the image."""
        pass

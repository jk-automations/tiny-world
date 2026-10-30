"""Tiny World for ComfyUI: one photo -> a tiny diorama world with an exact Blender camera move -> the real place.
Clone this repo into ComfyUI/custom_nodes/ (see README). Apache-2.0."""
import shutil
from pathlib import Path

from .tinyworld_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# Optional photo slots (giant guest, tiny me) need a file even when switched off: ship a blank placeholder into input/.
try:
    import folder_paths
    _blank = Path(folder_paths.get_input_directory()) / "tinyworld_blank.png"
    if not _blank.exists():
        shutil.copy(Path(__file__).parent / "templates" / "tinyworld_blank.png", _blank)
except Exception as e:  # never block ComfyUI start-up
    print(f"[Tiny World] could not place the blank placeholder: {e}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

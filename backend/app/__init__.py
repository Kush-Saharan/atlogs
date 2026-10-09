"""Atlas backend package.

Set HuggingFace Hub env vars at the earliest possible point — before any
submodule (embeddings/LLM clients, Docling) imports `huggingface_hub`, whose
constants are frozen at import time. On Windows without Developer Mode/admin,
HF's default symlinked cache raises WinError 1314 when Docling downloads its
layout/table models; copying instead of symlinking avoids it.
"""

import os

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

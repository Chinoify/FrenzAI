"""Voice blending service — create custom voices by mixing Kokoro voice tensors."""
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from app.config import settings


async def blend_kokoro_voices(
    voice_specs: list[dict],  # [{"code": "af_heart", "weight": 0.7}, ...]
    pipeline,  # KPipeline instance
) -> tuple[torch.Tensor, str]:
    """Blend multiple Kokoro voices by weighted average of their tensors.

    Returns (blended_tensor, saved_path).
    """
    if len(voice_specs) < 2:
        raise ValueError("Need at least 2 voices to blend")
    if len(voice_specs) > 4:
        raise ValueError("Maximum 4 voices for blending")

    # Normalize weights
    total_weight = sum(s["weight"] for s in voice_specs)
    if total_weight == 0:
        raise ValueError("Weights cannot all be zero")

    # Load and blend
    blended = None
    for spec in voice_specs:
        tensor = pipeline.load_voice(spec["code"])
        weight = spec["weight"] / total_weight
        if blended is None:
            blended = weight * tensor
        else:
            blended = blended + weight * tensor

    # Save as .pt file
    file_id = str(uuid.uuid4())
    pt_path = settings.embeddings_dir / f"{file_id}.pt"
    torch.save(blended, str(pt_path))

    # Also save a compatibility .npy (just the first slice flattened to 256)
    npy_path = settings.embeddings_dir / f"{file_id}.npy"
    compat = blended[0, 0, :].numpy().astype(np.float32)
    np.save(str(npy_path), compat)

    return blended, str(pt_path)


def load_blended_voice(pt_path: str) -> Optional[torch.Tensor]:
    """Load a previously saved blended voice tensor."""
    path = Path(pt_path)
    if path.exists() and path.suffix == ".pt":
        return torch.load(str(path), weights_only=True)
    return None

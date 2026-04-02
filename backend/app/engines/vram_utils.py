"""VRAM management utilities for GTX 970 (4GB dedicated + 12GB shared)."""
import gc


def print_vram(label: str = ""):
    """Print current VRAM usage."""
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / (1024 * 1024)
            reserved = torch.cuda.memory_reserved(0) / (1024 * 1024)
            print(f"[VRAM {label}] Allocated: {allocated:.0f}MB | Reserved: {reserved:.0f}MB")
    except Exception:
        pass


def cleanup_vram():
    """Aggressively free VRAM between model loads."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:
        pass


def get_torch_dtype():
    """Always use float16 for 4GB VRAM GPU."""
    try:
        import torch
        return torch.float16
    except ImportError:
        return None


def get_quantization_config():
    """Get 8-bit quantization config for models >4GB."""
    try:
        from transformers import BitsAndBytesConfig
        return BitsAndBytesConfig(load_in_8bit=True)
    except ImportError:
        return None


def safe_load_model(load_fn, model_name: str = "model"):
    """Wrapper that prints VRAM before/after and handles cleanup on failure."""
    print_vram(f"before loading {model_name}")
    try:
        model = load_fn()
        print_vram(f"after loading {model_name}")
        return model
    except Exception as e:
        print(f"[VRAM] Failed to load {model_name}: {e}")
        cleanup_vram()
        print_vram(f"after cleanup {model_name}")
        raise

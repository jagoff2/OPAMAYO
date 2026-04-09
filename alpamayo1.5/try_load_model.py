import os
import time
import traceback

import torch
from transformers import logging as hf_logging

from alpamayo1_5.models.alpamayo1_5 import Alpamayo1_5


hf_logging.set_verbosity_info()


def main() -> None:
    os.environ.setdefault("HF_HOME", "/mnt/g/hf")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

    print("torch", torch.__version__)
    print("cuda available", torch.cuda.is_available())
    print("cuda device count", torch.cuda.device_count())
    for i in range(torch.cuda.device_count()):
        print("gpu", i, torch.cuda.get_device_name(i), torch.cuda.mem_get_info(i))

    t0 = time.time()
    try:
        model = Alpamayo1_5.from_pretrained(
            "nvidia/Alpamayo-1.5-10B",
            dtype=torch.bfloat16,
            attn_implementation="eager",
            device_map="auto",
            max_memory={0: "15GiB", 1: "15GiB", "cpu": "96GiB"},
            low_cpu_mem_usage=True,
        )
    except Exception:
        print("load_failed_after_seconds", round(time.time() - t0, 2))
        traceback.print_exc()
        raise

    dt = time.time() - t0
    print("loaded_seconds", round(dt, 2))
    print("hf_device_map", getattr(model, "hf_device_map", None))
    print("model_device", next(model.parameters()).device)
    for i in range(torch.cuda.device_count()):
        free_b, total_b = torch.cuda.mem_get_info(i)
        print("gpu_post_load", i, {"used_gib": round((total_b - free_b) / (1024**3), 2), "total_gib": round(total_b / (1024**3), 2)})


if __name__ == "__main__":
    main()

import torch, time
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

ROOT = Path(__file__).resolve().parent.parent
DPO_ADAPTER = str(ROOT / "out" / "dpo_beta_050")
OUT_PATH = str(ROOT / "out" / "merged_model")
MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

print("[1/4] Loading base model in bf16...")
t0 = time.time()
base_model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16, device_map="cpu")
print(f"  Loaded in {time.time()-t0:.1f}s")

print("[2/4] Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

print("[3/4] Merging DPO adapter...")
t0 = time.time()
model = PeftModel.from_pretrained(base_model, DPO_ADAPTER)
model = model.merge_and_unload()
print(f"  Merged in {time.time()-t0:.1f}s")

print(f"[4/4] Saving to {OUT_PATH}...")
t0 = time.time()
model.save_pretrained(OUT_PATH, safe_serialization=True)
tokenizer.save_pretrained(OUT_PATH)
print(f"  Saved in {time.time()-t0:.1f}s")
print("Done.")

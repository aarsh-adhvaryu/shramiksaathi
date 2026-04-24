"""
ShramikSaathi — Stage 2.2: DPO Training with Beta Sweep

Trains 3 DPO adapters on top of the Stage 1 SFT LoRA (out/lora_v2),
one per beta value: {0.05, 0.10, 0.20}.

DPO config (proposal-aligned):
  - Base: LLaMA 3.1 8B Instruct (4-bit NF4) + SFT LoRA (out/lora_v2) frozen as reference
  - Trainable: new LoRA adapter on top, rank 16 alpha 32
  - Beta sweep: 0.05, 0.10, 0.20
  - 2 epochs per beta (DPO converges faster than SFT)
  - lr 5e-6 (standard for DPO on top of SFT'd model)
  - Effective batch 8 (per-device 1 x grad-accum 8) — DPO doubles VRAM per sample
  - 15% val split, stratified by dimension

Inputs:
  data/dpo_pairs.jsonl   (373 pairs)
  out/lora_v2/           (Stage 1 SFT LoRA)

Outputs:
  out/dpo_beta_005/  out/dpo_beta_010/  out/dpo_beta_020/
  data/dpo_training_log.json  (per-beta loss curves + val metrics)

Run from project root on Lightning:
    python scripts/train_dpo.py
"""

import os
import json
import time
import random
from pathlib import Path

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from peft import LoraConfig, PeftModel, prepare_model_for_kbit_training
from trl import DPOTrainer, DPOConfig


# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH     = PROJECT_ROOT / "data" / "dpo_pairs.jsonl"
SFT_ADAPTER   = PROJECT_ROOT / "out" / "lora_v2"
OUT_ROOT      = PROJECT_ROOT / "out"
LOG_PATH      = PROJECT_ROOT / "data" / "dpo_training_log.json"

MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

# Beta sweep
BETA_VALUES = [0.05, 0.10, 0.20]

# LoRA for DPO (separate adapter on top of SFT LoRA)
LORA_RANK     = 16
LORA_ALPHA    = 32
LORA_DROPOUT  = 0.05
LORA_TARGETS  = ["q_proj", "k_proj", "v_proj", "o_proj",
                 "gate_proj", "up_proj", "down_proj"]

# Training
NUM_EPOCHS        = 2
PER_DEVICE_BATCH  = 1          # DPO processes chosen+rejected together; halves the batch
GRAD_ACCUM        = 8          # effective batch = 8
LEARNING_RATE     = 5e-6
WARMUP_RATIO      = 0.1
MAX_LENGTH        = 2048
MAX_PROMPT_LENGTH = 1600
LOGGING_STEPS     = 5
EVAL_STEPS        = 20
SAVE_STEPS        = 20
VAL_FRACTION      = 0.15
SEED              = 42

random.seed(SEED)


# ════════════════════════════════════════════════════════════════════════════
# DATA LOAD + SPLIT
# ════════════════════════════════════════════════════════════════════════════

def load_dpo_pairs():
    """Load pairs and produce (prompt, chosen, rejected) triples.
    Splits 15% into val, stratified by dimension."""
    rows = []
    with open(DATA_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            # DPOTrainer expects: prompt, chosen, rejected
            rows.append({
                "prompt":   r["full_prompt"],
                "chosen":   r["chosen"],
                "rejected": r["rejected"],
                "dimension": r["metadata"]["dimension"],
                "domain":    r["metadata"]["domain"],
            })
    print(f"[Data] {len(rows)} DPO pairs loaded")

    # Stratified split
    from collections import defaultdict
    by_dim = defaultdict(list)
    for r in rows:
        by_dim[r["dimension"]].append(r)

    train, val = [], []
    for dim, dim_rows in by_dim.items():
        random.shuffle(dim_rows)
        n_val = max(1, int(len(dim_rows) * VAL_FRACTION))
        val.extend(dim_rows[:n_val])
        train.extend(dim_rows[n_val:])

    random.shuffle(train)
    random.shuffle(val)

    # Strip metadata — DPOTrainer only needs prompt/chosen/rejected
    train = [{k: v for k, v in r.items() if k in ("prompt", "chosen", "rejected")} for r in train]
    val   = [{k: v for k, v in r.items() if k in ("prompt", "chosen", "rejected")} for r in val]

    print(f"       Train: {len(train)}  Val: {len(val)}")

    train_ds = Dataset.from_list(train)
    val_ds   = Dataset.from_list(val)
    return train_ds, val_ds


# ════════════════════════════════════════════════════════════════════════════
# MODEL LOADING
# ════════════════════════════════════════════════════════════════════════════

def load_base_with_sft():
    """
    Load base LLaMA 3.1 8B in 4-bit, attach SFT LoRA on top (as trainable).
    Returns (model, tokenizer, device). The SFT LoRA weights will be further
    trained via DPO — this is standard "continue training" pattern.
    """
    print(f"Loading base {MODEL_ID} in 4-bit NF4")
    t0 = time.time()
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"  # DPO needs left padding for generation-style loss

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        attn_implementation="sdpa",
    )
    print(f"  Base loaded in {time.time()-t0:.1f}s | VRAM {torch.cuda.memory_allocated()/1e9:.2f}GB")
    model.config.use_cache = False

    # Attach SFT LoRA as a STARTING POINT for further training
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = PeftModel.from_pretrained(model, str(SFT_ADAPTER), is_trainable=True)

    # Confirm the adapter is trainable
    model.print_trainable_parameters()

    device = next(model.parameters()).device
    return model, tokenizer, device


# ════════════════════════════════════════════════════════════════════════════
# TRAIN ONE BETA
# ════════════════════════════════════════════════════════════════════════════

def train_one_beta(beta, train_ds, val_ds, log_collector):
    beta_tag = f"{int(beta*1000):03d}"
    out_dir = OUT_ROOT / f"dpo_beta_{beta_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 70}")
    print(f"Training DPO | beta = {beta} | out = {out_dir}")
    print(f"{'=' * 70}")

    model, tokenizer, device = load_base_with_sft()

    dpo_config = DPOConfig(
        output_dir=str(out_dir),
        beta=beta,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=PER_DEVICE_BATCH,
        per_device_eval_batch_size=PER_DEVICE_BATCH,
        gradient_accumulation_steps=GRAD_ACCUM,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        learning_rate=LEARNING_RATE,
        lr_scheduler_type="cosine",
        warmup_ratio=WARMUP_RATIO,
        bf16=True,
        fp16=False,
        logging_steps=LOGGING_STEPS,
        eval_strategy="steps",
        eval_steps=EVAL_STEPS,
        save_strategy="steps",
        save_steps=SAVE_STEPS,
        save_total_limit=1,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        optim="paged_adamw_8bit",
        weight_decay=0.01,
        max_grad_norm=1.0,
        max_length=MAX_LENGTH,
        max_prompt_length=MAX_PROMPT_LENGTH,
        seed=SEED,
        report_to="none",
        push_to_hub=False,
        remove_unused_columns=False,
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=None,   # when ref_model=None, DPOTrainer uses the model with adapter disabled as reference
        args=dpo_config,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
    )

    t0 = time.time()
    trainer.train()
    train_mins = (time.time() - t0) / 60

    # Final eval
    eval_metrics = trainer.evaluate()

    # Save
    trainer.model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    log_collector[f"beta_{beta_tag}"] = {
        "beta":            beta,
        "num_epochs":      NUM_EPOCHS,
        "learning_rate":   LEARNING_RATE,
        "train_runtime_min": round(train_mins, 2),
        "final_eval":      eval_metrics,
        "log_history":     trainer.state.log_history,
    }
    print(f"  [beta={beta}] eval_loss={eval_metrics.get('eval_loss', 'n/a')}")
    print(f"  [beta={beta}] trained in {train_mins:.1f}min")

    # Free VRAM before next beta
    del trainer
    del model
    torch.cuda.empty_cache()


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("ShramikSaathi — Stage 2.2: DPO Training with Beta Sweep")
    print("=" * 70)

    train_ds, val_ds = load_dpo_pairs()

    log_collector = {
        "base_model":      MODEL_ID,
        "sft_adapter":     str(SFT_ADAPTER),
        "n_train":         len(train_ds),
        "n_val":           len(val_ds),
        "lora_rank":       LORA_RANK,
        "lora_alpha":      LORA_ALPHA,
        "beta_values":     BETA_VALUES,
    }

    for beta in BETA_VALUES:
        try:
            train_one_beta(beta, train_ds, val_ds, log_collector)
        except Exception as e:
            import traceback
            print(f"\n[ERROR] beta={beta} failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            log_collector[f"beta_{int(beta*1000):03d}"] = {"error": str(e)}

    with open(LOG_PATH, "w") as f:
        json.dump(log_collector, f, indent=2, default=str)

    print(f"\n{'=' * 70}")
    print("Stage 2.2 complete.")
    print(f"{'=' * 70}")
    for beta in BETA_VALUES:
        key = f"beta_{int(beta*1000):03d}"
        info = log_collector.get(key, {})
        if "error" in info:
            print(f"  beta={beta}: FAILED — {info['error'][:80]}")
        else:
            final = info.get("final_eval", {})
            print(f"  beta={beta}: eval_loss={final.get('eval_loss', 'n/a')}")
    print(f"\n  Training log: {LOG_PATH}")
    print(f"  Adapters: out/dpo_beta_005  out/dpo_beta_010  out/dpo_beta_020")
    print(f"\nNext step: run scripts/eval_dpo.py to compare adapters on held-out eval.")


if __name__ == "__main__":
    main()
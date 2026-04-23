"""
ShramikSaathi — Stage 1.2: LoRA SFT on LLaMA 3.1 8B

Trains a LoRA adapter on the 285-example SFT dataset.

Spec (proposal-aligned):
  - Base model: meta-llama/Llama-3.1-8B-Instruct
  - Rank 16, Alpha 32, Dropout 0.05
  - Target modules: all attention + MLP projections
  - 3 epochs, lr 2e-4, cosine schedule, warmup 0.03
  - Effective batch 16 (per-device 2 x grad-accum 8)
  - bf16 mixed precision
  - 4-bit NF4 quantization on the base model
  - Max seq length 2048
  - Gradient checkpointing ON
  - Seed 42

Inputs:
  data/sft_train.jsonl  (285 rows, messages format)
  data/sft_val.jsonl    (21 rows)

Outputs:
  out/lora_v2/                   Local adapter directory (best checkpoint)
  out/lora_v2/training_log.json  Loss curve + final metrics
  HF: aarsh-adhvaryu/shramik-saathi-lora-v2

Run from project root on Lightning:
    python scripts/train_lora.py
"""

import os
import json
import time
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, prepare_model_for_kbit_training, PeftModel
from trl import SFTTrainer, SFTConfig


# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAIN_PATH = PROJECT_ROOT / "data" / "sft_train.jsonl"
VAL_PATH = PROJECT_ROOT / "data" / "sft_val.jsonl"
OUT_DIR = PROJECT_ROOT / "out" / "lora_v2"
LOG_PATH = OUT_DIR / "training_log.json"

MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
HF_REPO = "aarsh-adhvaryu/shramik-saathi-lora-v2"

# LoRA (proposal-spec)
LORA_RANK = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LORA_TARGETS = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]

# Training
NUM_EPOCHS = 3
PER_DEVICE_BATCH = 2
GRAD_ACCUM = 8  # effective batch = 16
LEARNING_RATE = 2e-4
WARMUP_RATIO = 0.03
MAX_SEQ_LEN = 2048
LOGGING_STEPS = 5
EVAL_STEPS = 25
SAVE_STEPS = 25
SEED = 42


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════


def main():
    print("=" * 70)
    print("ShramikSaathi — Stage 1.2: LoRA SFT Training")
    print("=" * 70)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load dataset ────────────────────────────────────────────────────────
    print(f"\n[Data] Loading from {TRAIN_PATH}, {VAL_PATH}")
    dataset = load_dataset(
        "json",
        data_files={
            "train": str(TRAIN_PATH),
            "validation": str(VAL_PATH),
        },
    )
    print(f"       Train: {len(dataset['train'])}  Val: {len(dataset['validation'])}")
    print(f"       Keys:  {list(dataset['train'][0].keys())}")

    # ── Tokenizer ────────────────────────────────────────────────────────────
    print(f"\n[Tokenizer] Loading {MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"  # required for training (vs 'left' for generation)
    print(f"            Chat template set: {tokenizer.chat_template is not None}")

    # ── Quantization + Base model ───────────────────────────────────────────
    print(f"\n[Model] Loading {MODEL_ID} in 4-bit NF4")
    t0 = time.time()
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        attn_implementation="sdpa",
    )
    print(f"        Loaded in {time.time()-t0:.1f}s")
    print(f"        VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    # ── LoRA ────────────────────────────────────────────────────────────────
    print(f"\n[LoRA] rank={LORA_RANK} alpha={LORA_ALPHA} dropout={LORA_DROPOUT}")
    lora_config = LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=LORA_TARGETS,
        bias="none",
        task_type="CAUSAL_LM",
    )

    # ── SFTConfig (training args) ──────────────────────────────────────────
    sft_config = SFTConfig(
        output_dir=str(OUT_DIR),
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
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        optim="paged_adamw_8bit",
        weight_decay=0.01,
        max_grad_norm=1.0,
        max_seq_length=MAX_SEQ_LEN,
        packing=False,
        dataset_kwargs={"skip_prepare_dataset": False},
        seed=SEED,
        report_to="none",
        push_to_hub=False,  # push manually at the end for more control
        remove_unused_columns=False,
    )

    # ── Trainer ─────────────────────────────────────────────────────────────
    print(f"\n[Trainer] Building SFTTrainer")
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        peft_config=lora_config,
        tokenizer=tokenizer,
    )

    # Verify LoRA parameter counts before training
    try:
        trainer.model.print_trainable_parameters()
    except Exception:
        pass

    # ── Train ───────────────────────────────────────────────────────────────
    print(f"\n[Train] Starting training")
    print(f"        Effective batch: {PER_DEVICE_BATCH * GRAD_ACCUM}")
    print(
        f"        Steps/epoch:     ~{len(dataset['train']) // (PER_DEVICE_BATCH * GRAD_ACCUM)}"
    )
    print(
        f"        Total steps:     ~{NUM_EPOCHS * len(dataset['train']) // (PER_DEVICE_BATCH * GRAD_ACCUM)}"
    )

    t_train = time.time()
    train_result = trainer.train()
    train_mins = (time.time() - t_train) / 60
    print(f"\n[Train] Completed in {train_mins:.1f} min")

    # ── Final eval ──────────────────────────────────────────────────────────
    print(f"\n[Eval] Running final evaluation on validation set")
    eval_metrics = trainer.evaluate()
    print(f"       {json.dumps(eval_metrics, indent=2)}")

    # ── Save adapter locally ────────────────────────────────────────────────
    print(f"\n[Save] Writing adapter to {OUT_DIR}")
    trainer.model.save_pretrained(str(OUT_DIR))
    tokenizer.save_pretrained(str(OUT_DIR))

    # ── Training log ────────────────────────────────────────────────────────
    log_entries = trainer.state.log_history
    training_log = {
        "base_model": MODEL_ID,
        "lora_rank": LORA_RANK,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": LORA_DROPOUT,
        "num_epochs": NUM_EPOCHS,
        "effective_batch": PER_DEVICE_BATCH * GRAD_ACCUM,
        "learning_rate": LEARNING_RATE,
        "train_samples": len(dataset["train"]),
        "val_samples": len(dataset["validation"]),
        "train_runtime_min": round(train_mins, 2),
        "final_metrics": eval_metrics,
        "log_history": log_entries,
    }
    with open(LOG_PATH, "w") as f:
        json.dump(training_log, f, indent=2, default=str)
    print(f"       Training log: {LOG_PATH}")

    # ── Push to HF ──────────────────────────────────────────────────────────
    print(f"\n[HF] Pushing adapter to {HF_REPO}")
    try:
        trainer.model.push_to_hub(HF_REPO, private=True)
        tokenizer.push_to_hub(HF_REPO, private=True)
        print(f"     Pushed successfully")
    except Exception as e:
        print(f"     Push failed: {e}")
        print(f"     Adapter is saved locally at {OUT_DIR} — retry manually if needed.")

    print(f"\n{'=' * 70}")
    print(f"Stage 1.2 complete.")
    print(f"  Adapter: {OUT_DIR}")
    print(f"  HF:      {HF_REPO}")
    print(f"  Eval:    loss={eval_metrics.get('eval_loss', 'n/a'):.4f}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

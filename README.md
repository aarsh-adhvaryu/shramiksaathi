# ShramikSaathi — Indian Worker Rights AI Copilot

**RAG · ReAct Agent · DPO Alignment · Procedural Eligibility Reasoning**

> A grounded conversational copilot covering PF/EPFO, payslip audit, labour rights, and income tax — built on LLaMA 3.1 8B with LoRA SFT + DPO alignment.

[![Demo](https://img.shields.io/badge/Demo-Gradio-orange)](https://github.com/aarsh-adhvaryu/shramiksaathi)
[![Model-SFT](https://img.shields.io/badge/SFT_Adapter-HuggingFace-yellow)](https://huggingface.co/aarsh-adhvaryu/shramik-saathi-lora-v2)
[![Model-DPO](https://img.shields.io/badge/DPO_Adapter-HuggingFace-yellow)](https://huggingface.co/aarsh-adhvaryu/shramik-saathi-dpo-beta050)
[![Model-Merged](https://img.shields.io/badge/Merged_Model-HuggingFace-yellow)](https://huggingface.co/aarsh-adhvaryu/shramik-saathi-merged)
[![Report](https://img.shields.io/badge/Report-ACL_Format-blue)](#report)

---

## What is ShramikSaathi?

50 crore Indian workers have no reliable AI support for PF, salary, labour rights, and income tax queries. ShramikSaathi is the first grounded, end-to-end AI copilot that:

- **Audits payslips** — verifies EPF, ESI, professional tax deductions against statutory rates
- **Explains rights with citations** — every claim backed by doc_id from Acts and circulars
- **Checks eligibility** — verifies IF/THEN conditions before answering (not after)
- **Escalates appropriately** — suggests grievance portals when KB is insufficient

## Key Results

| Component | Metric | Baseline | Ours | Δ |
|---|---|---|---|---|
| Router | Accuracy | 0.818 | 0.909 | +0.091 |
| Slot Extractor | Recall | 0.865 | 0.973 | +0.108 |
| Sufficiency Gate | Accuracy | 0.500 | 0.991 | +0.491 |
| Retriever | MRR@5 | 0.668 | 0.725 | +0.057 |
| **Condition Coverage ★** | **Score** | **0.000** | **0.714** | **+0.714** |
| Generator | grounded_clean | 0.700 | 0.750 | +0.050 |
| RAGAS | Faithfulness | 0.830 | 0.800 | -0.030 |
| RAGAS | Answer Relevance | 0.950 | 0.960 | +0.010 |

★ Novel metric — measures whether the system verified eligibility conditions before answering.

## Architecture

```
User Query → Cross-domain Router → Slot Extractor → Sufficiency Gate
                                                          ↓
                                              FAISS Retrieval (311 docs)
                                              + Domain-aware filtering
                                                          ↓
                                          Eligibility Reasoner (novel)
                                            ↓ RESOLVED / WARNING / ESCALATE
                                              Generator (LLaMA 3.1 8B + DPO)
                                              + Citation post-processing
                                                          ↓
                                                  Cited Answer + Next Steps
```

Nine-layer pipeline with three novel contributions:
1. **Procedural Eligibility Reasoner** — parses IF/THEN conditions, checks against slots
2. **Cross-domain Slot Router** — one system, four domains
3. **Condition Coverage Score** — novel evaluation metric

## Models on HuggingFace

| Component | Model | HuggingFace Repo |
|---|---|---|
| Generator (SFT) | LLaMA 3.1 8B + LoRA | [aarsh-adhvaryu/shramik-saathi-lora-v2](https://huggingface.co/aarsh-adhvaryu/shramik-saathi-lora-v2) |
| Generator (DPO) | LLaMA 3.1 8B + DPO β=0.05 | [aarsh-adhvaryu/shramik-saathi-dpo-beta050](https://huggingface.co/aarsh-adhvaryu/shramik-saathi-dpo-beta050) |
| Merged Model | LLaMA 3.1 8B + DPO (merged weights) | [aarsh-adhvaryu/shramik-saathi-merged](https://huggingface.co/aarsh-adhvaryu/shramik-saathi-merged) |
| Base Model | meta-llama/Llama-3.1-8B-Instruct | [HuggingFace Hub](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) |
| Retriever | all-MiniLM-L6-v2 | [sentence-transformers](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) |

---

## Setup — Local Machine (Consumer GPU)

Tested on: **RTX 5070 Ti (12GB)**, RTX 4090 (24GB), RTX 3090 (24GB)

### Prerequisites

- Python 3.10+
- NVIDIA GPU with 12GB+ VRAM
- CUDA 12.1+ drivers
- ~20GB disk space (15GB base model + adapters + data)

### 1. Clone and set up

```bash
git clone https://github.com/aarsh-adhvaryu/shramiksaathi.git
cd shramiksaathi
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 2. Install PyTorch (GPU-specific)

```bash
# RTX 5070 Ti / 50-series (Blackwell) — CUDA 12.8
pip install torch --index-url https://download.pytorch.org/whl/cu128

# RTX 4090 / 40-series (Ada) — CUDA 12.6
pip install torch --index-url https://download.pytorch.org/whl/cu126

# RTX 3090 / 30-series (Ampere) — CUDA 12.4
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Verify GPU

```bash
python -c "import torch; print(torch.cuda.get_device_name(0)); import bitsandbytes; print('OK')"
```

If bitsandbytes fails, see [Troubleshooting](#troubleshooting).

### 5. Download adapter weights

```bash
# SFT adapter (168MB)
huggingface-cli download aarsh-adhvaryu/shramik-saathi-lora-v2 --local-dir out/lora_v2/

# DPO adapter (168MB)
huggingface-cli download aarsh-adhvaryu/shramik-saathi-dpo-beta050 --local-dir out/dpo_beta_050/
```

The base model (~15GB) downloads automatically on first run.

### 6. Run

```bash
python app.py
```

Opens at **http://localhost:7860** — ~18-25s per query on RTX 5070 Ti.

---

## Setup — Lightning AI (Training + Evaluation)

Used for: DPO training, LoRA SFT, retriever fine-tuning, running evaluations.

### 1. Open a Lightning AI studio with A100 80GB

### 2. Clone and install

```bash
cd ~
git clone https://github.com/aarsh-adhvaryu/shramiksaathi.git
cd shramiksaathi

pip install torch transformers==4.46.3 peft==0.13.2 trl==0.12.2 \
    bitsandbytes accelerate sentence-transformers faiss-cpu gradio \
    rank-bm25 groq python-dotenv ragas --break-system-packages
```

### 3. Download adapter weights

```bash
huggingface-cli download aarsh-adhvaryu/shramik-saathi-lora-v2 --local-dir out/lora_v2/
huggingface-cli download aarsh-adhvaryu/shramik-saathi-dpo-beta050 --local-dir out/dpo_beta_050/
```

### 4. Set up Groq API (for evals only)

```bash
echo "GROQ_API_KEY=your_key_here" > .env
```

### 5. Run the demo

```bash
python app.py
```

Gradio launches with a public share URL (valid 1 week).

### 6. Run training (if retraining)

```bash
# Stage 1: Retriever fine-tuning
python scripts/finetune_retriever.py

# Stage 2: LoRA SFT (~9 min on A100)
python scripts/train_lora.py

# Stage 3: DPO with beta sweep (~30 min on A100)
python scripts/train_dpo.py
```

### 7. Run evaluations

```bash
# DPO evaluation (20 prompts × 4 systems, ~40 min)
python scripts/eval_dpo.py

# Full eval suite
python eval/ablation_runner.py 2>&1 | tee data/ablation.log
```

---

## Demo Features

The Gradio interface has three panels:

- **Chat** — multi-turn conversation with slot accumulation across turns
- **Evaluation tab** — live per-query metrics: domain, intent, slots filled, condition coverage, citations (grounded/fabricated), total latency
- **Pipeline Trace tab** — step-by-step view: Router+Slots → Gate → FAISS Retrieval → Eligibility Reasoner → Generator

### Example queries

```
# Gratuity (labour domain)
I worked for 6 years in a private company, terminated without notice. Am I eligible for gratuity?

# PF withdrawal (PF domain — multi-turn)
I resigned 3 months ago, UAN is active. Can I withdraw my full PF?
→ System asks: "Is your KYC complete?" → Answer: "yes"
→ CCS goes from 0.75 → 1.0 across turns

# Payslip audit (payslip domain)
My basic salary is 20000, EPF deducted is 1200. Is this correct?

# Tax (tax domain)
I earn 8 lakh per year on old regime. Can I claim 80C deduction for PPF and ELSS?
```

---

## Serving Optimizations

Three optimizations reduce latency from 50-70s to 18-25s:

| Optimization | What it does | Speedup |
|---|---|---|
| **Adapter toggle** | Disables DPO adapter for routing/slots (base LLaMA gives cleaner JSON), re-enables for generation | Router: 8s → 3s |
| **Deterministic reasoner** | Pre-cached eligibility rules in JSON replace LLM condition parser | Reasoner: 15-40s → <0.1s |
| **Citation post-processing** | Regex strips fabricated doc_ids not in KB | Guarantees 0 fabrication |

| Pipeline Step | Eval (A100) | Demo (RTX 5070 Ti) |
|---|---|---|
| Router + Slots | 5-8s | 2-4s |
| FAISS Retrieval | <0.1s | <0.1s |
| Eligibility Reasoner | 15-40s | <0.1s |
| Generator | 25-30s | 15-20s |
| **Total** | **50-70s** | **18-25s** |

---

## Training

### Stage 1: Retriever Fine-tuning

```bash
python scripts/finetune_retriever.py
```

Fine-tunes all-MiniLM-L6-v2 on 916 (query, positive, hard_negative) triplets with BM25-mined hard negatives. Triplet loss, margin 0.3, 3 epochs.

### Stage 2: LoRA SFT

```bash
python scripts/train_lora.py
```

Fine-tunes LLaMA 3.1 8B Instruct with LoRA (rank 16, α=32) on 285 examples. 4-bit NF4, 3 epochs, ~9 min on A100. 42M trainable params (0.52% of 8B).

### Stage 3: DPO Alignment

```bash
python scripts/train_dpo.py
```

373 preference pairs across 4 dimensions:
- **Grounding** (110 pairs) — cite real doc_ids vs fabricated prerequisites
- **Verdict correctness** (110 pairs) — correct eligibility vs flipped verdicts
- **Citation discipline** (100 pairs) — right doc_id on right claim vs shuffled
- **Refusal & escalation** (53 pairs) — appropriate refusal vs hallucinated answers

Beta sweep {0.05, 0.10, 0.20}. Winner: β=0.05 (grounded_clean 0.750, zero fabrication). ~10 min/beta on A100.

---

## Evaluation

### DPO Beta Sweep (20 held-out prompts)

| System | Grounded | Fabrication | Citations | Verdict |
|---|---|---|---|---|
| SFT-only | 0.700 | 0.000 | 0.800 | 0.700 |
| **DPO β=0.05** | **0.750** | **0.000** | **0.850** | **0.750** |
| DPO β=0.10 | 0.700 | 0.000 | 0.750 | 0.700 |
| DPO β=0.20 | 0.700 | 0.000 | 0.700 | 0.700 |

### System-Level Ablation (20 prompts)

| Config | Grounded | CCS | Fabrication | Verdict |
|---|---|---|---|---|
| A: Vanilla RAG | 0.550 | 0.000 | 0.050 | 0.550 |
| B: +Pre-retrieval | 0.800 | 0.000 | 0.050 | 0.800 |
| C: +Reasoner | 0.700 | 0.631 | 0.000 | 0.700 |
| D: Full system | 0.700 | 0.647 | 0.050 | 0.750 |

### Per-Domain Breakdown

| Domain | Retriever R@5 | CCS | SFT Grounded | DPO Grounded |
|---|---|---|---|---|
| PF | 0.367 | 0.640 | 0.40 | 0.40 |
| Payslip | 0.467 | 0.738 | 0.60 | 0.80 |
| Labour | 0.933 | 0.750 | 1.00 | 1.00 |
| Tax | 1.000 | 0.750 | 0.80 | 0.80 |

All evaluation results are saved in `data/*_results.json`.

---

## Project Structure

```
shramiksaathi/
├── app.py                      # Gradio demo (fully local, adapter toggle)
├── setup_local.py              # Automated local setup script
├── requirements.txt            # Clean dependencies (15 packages)
├── step1_create_rules.py       # Creates eligibility_rules.json
├── step2_patch_reasoner.py     # Patches app.py with deterministic reasoner
│
├── src/
│   ├── pipeline.py             # Full pipeline orchestrator
│   ├── cross_domain_router.py  # Keyword baseline + LLM router
│   ├── slot_extractor.py       # Regex baseline + LLM extractor
│   ├── sufficiency_gate.py     # Rule-based gate
│   ├── react_loop.py           # ReAct with SearchKB/GetPolicy/ParsePayslip
│   ├── eligibility_reasoner.py # Condition Parser + Checker + Gap Resolver
│   ├── search_kb.py            # FAISS search wrapper
│   ├── bm25_retriever.py       # BM25 baseline retriever
│   └── tools.py                # ParsePayslip calculator + tool stubs
│
├── eval/
│   ├── router_eval_runner.py
│   ├── slot_eval_runner.py
│   ├── sufficiency_eval_runner.py
│   ├── retriever_eval_runner.py
│   ├── condition_coverage_eval.py
│   ├── ragas_eval_runner.py
│   └── ablation_runner.py      # 4-config system-level ablation
│
├── scripts/
│   ├── train_lora.py           # Stage 2: LoRA SFT
│   ├── train_dpo.py            # Stage 3: DPO with beta sweep
│   ├── eval_dpo.py             # DPO held-out evaluation
│   ├── finetune_retriever.py   # Stage 1: Retriever fine-tuning
│   ├── merge_adapter.py        # Merge DPO adapter into base weights
│   ├── generate_sft_dataset.py
│   └── generate_dpo_dataset.py
│
├── data/
│   ├── kb.jsonl                # 311 KB documents (4 domains)
│   ├── eligibility_rules.json  # Pre-cached eligibility conditions
│   ├── sft_train.jsonl         # 285 SFT training examples
│   ├── dpo_pairs.jsonl         # 373 DPO preference pairs
│   ├── eval_heldout.jsonl      # 20 held-out evaluation prompts
│   └── *_results.json          # All evaluation results
│
├── index/
│   ├── faiss_index.bin         # FAISS vector index
│   └── chunk_store.json        # doc_id → text + metadata
│
└── out/                        # Adapter weights (git-ignored, on HuggingFace)
    ├── lora_v2/                # SFT adapter
    └── dpo_beta_050/           # DPO winner (β=0.05)
```

## Technology Stack

| Component | Technology |
|---|---|
| Base LLM | LLaMA 3.1 8B Instruct |
| Fine-tuning | LoRA (PEFT 0.13.2) + DPO (TRL 0.12.2) |
| Quantization | 4-bit NF4 (bitsandbytes) |
| Retrieval | FAISS IndexFlatL2 + sentence-transformers |
| Encoder | all-MiniLM-L6-v2 (384-dim) |
| Pipeline | Custom Python (no LangChain) |
| Demo | Gradio |
| Training | Lightning AI A100 80GB |
| Local inference | RTX 5070 Ti 12GB (CUDA 12.8) |

## Troubleshooting

**"Torch not compiled with CUDA enabled"** — You installed CPU-only PyTorch. Reinstall with the correct CUDA index URL (see step 2 above).

**"bitsandbytes not found" or crashes** — Try `pip install bitsandbytes>=0.44.0`. If it still fails, edit `app.py` to use fp16 instead of 4-bit:
```python
# Replace BitsAndBytesConfig block with:
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, torch_dtype=torch.float16,
    device_map="auto", attn_implementation="sdpa",
)
```
This uses ~16GB VRAM instead of ~6GB.

**"adapter_model.safetensors not found"** — Run the huggingface-cli download commands from step 5.

**"CUDA out of memory"** — Close other GPU apps. RTX 5070 Ti (12GB) fits 4-bit with ~6GB headroom.

**Slow first run (~2 min)** — Base model downloading from HuggingFace. Subsequent runs start in ~10-30s.

**"No CUDA GPUs are available"** — Check `nvidia-smi` works. Update GPU drivers if needed.

---

## Known Limitations

- **PF domain** grounded_clean stuck at 0.40 — large overlapping KB (240 docs) causes retrieval near-misses
- **ReAct loop** occasionally fabricates user facts in reasoning traces — demo uses direct FAISS retrieval instead
- **DPO dataset** underrepresents tax (10/373 pairs) and refusal dimension (53/80 target)
- **Multi-turn domain drift** — short follow-up answers can trigger re-routing; mitigated with follow-up detection
- **Cross-encoder reranker** from proposal was not implemented due to time constraints

## Novel Contributions

1. **Procedural Eligibility Reasoner** — extracts and verifies IF/THEN condition chains before generation. No existing RAG system does this explicitly.
2. **Condition Coverage Score** — novel metric measuring pre-answer eligibility verification. Baseline = 0.000 by construction, ours = 0.714.
3. **4-dimension DPO rubric** — grounding, verdict correctness, citation discipline, refusal/escalation — designed for support workflows rather than generic helpfulness.

## Citation

```bibtex
@article{adhvaryu2026shramiksaathi,
  title={ShramikSaathi: A Grounded Multi-Domain Copilot for Indian Worker Rights 
         with Procedural Eligibility Reasoning and DPO Alignment},
  author={Adhvaryu, Aarsh and Sharma, Nikita and Lamba, Srishti and Agrawal, Mannan},
  journal={DS615: Neural Networks and Deep Learning, Course Project},
  year={2026}
}
```

## Acknowledgments

- Prof. Sourish Dasgupta — project guidance and evaluation framework
- Lightning AI — A100 student compute credits
- Knowledge base constructed from publicly available Indian Acts, EPFO circulars, court rulings, and state government notifications

## License

Academic project. Knowledge base documents are derived from publicly available Indian government publications.

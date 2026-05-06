# ShramikSaathi — Indian Worker Rights AI Copilot

**RAG · ReAct Agent · DPO Alignment · Procedural Eligibility Reasoning**

> A grounded conversational copilot covering PF/EPFO, payslip audit, labour rights, and income tax — built on LLaMA 3.1 8B with LoRA SFT + DPO alignment.

[![Demo](https://img.shields.io/badge/Demo-Gradio-orange)](https://github.com/aarsh-adhvaryu/shramiksaathi)
[![Model](https://img.shields.io/badge/Model-HuggingFace-yellow)](https://huggingface.co/aarsh-adhvaryu/shramik-saathi-lora-v2)
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
| Generator | grounded_clean | 0.650 | 0.750 | +0.100 |

★ Novel metric — measures whether the system verified eligibility conditions before answering.

## Architecture

```
User Query → Cross-domain Router → Slot Extractor → Sufficiency Gate
                                                          ↓
                                              FAISS Retrieval (311 docs)
                                                          ↓
                                          Eligibility Reasoner (novel)
                                            ↓ RESOLVED / WARNING / ESCALATE
                                              Generator (LLaMA 3.1 8B + DPO)
                                                          ↓
                                                  Cited Answer + Next Steps
```

Nine-layer pipeline with three novel contributions:
1. **Procedural Eligibility Reasoner** — parses IF/THEN conditions, checks against slots
2. **Cross-domain Slot Router** — one system, four domains
3. **Condition Coverage Score** — novel evaluation metric

## Models & Weights

| Component | Model | Location |
|---|---|---|
| Generator (SFT) | LLaMA 3.1 8B + LoRA | [HuggingFace](https://huggingface.co/aarsh-adhvaryu/shramik-saathi-lora-v2) |
| Generator (DPO) | LLaMA 3.1 8B + DPO β=0.05 | `out/dpo_beta_050/` (local) |
| Retriever | all-MiniLM-L6-v2 (fine-tuned) | `out/retriever_finetuned/` (local) |
| Base Model | meta-llama/Llama-3.1-8B-Instruct | HuggingFace Hub |

## Quick Start

### Prerequisites

- Python 3.10+
- CUDA-capable GPU (A100 80GB recommended, 24GB+ minimum with 4-bit quantization)
- ~15GB disk space for model weights

### 1. Clone the repo

```bash
git clone https://github.com/aarsh-adhvaryu/shramiksaathi.git
cd shramiksaathi
```

### 2. Install dependencies

```bash
pip install torch transformers peft trl bitsandbytes accelerate \
    sentence-transformers faiss-cpu gradio rank-bm25 \
    groq python-dotenv --break-system-packages
```

### 3. Set up environment

```bash
# Only needed if running evals with Groq (not needed for demo)
echo "GROQ_API_KEY=your_key_here" > .env
```

### 4. Download model weights

The base model downloads automatically from HuggingFace on first run. The DPO adapter and fine-tuned retriever must be present locally:

```
out/
├── dpo_beta_050/           # DPO winner adapter
│   ├── adapter_config.json
│   └── adapter_model.safetensors
├── lora_v2/                # SFT adapter
│   ├── adapter_config.json
│   └── adapter_model.safetensors
└── retriever_finetuned/    # Fine-tuned MiniLM encoder
```

### 5. Run the demo

```bash
python app.py
```

This will:
- Load the FAISS index (311 documents)
- Load the fine-tuned retriever encoder
- Load LLaMA 3.1 8B + DPO adapter in 4-bit quantization
- Launch a Gradio interface on `http://0.0.0.0:7860`
- Print a public share URL (valid for 1 week)

**Demo features:**
- Chat interface with multi-turn conversation
- **Evaluation tab** — live per-query metrics (citations, fabrication check, condition coverage, latency)
- **Pipeline Trace tab** — step-by-step view of router → slots → gate → retrieval → reasoner → generator

### Example queries to try

```
# Gratuity (labour domain — scores 1.00 grounded_clean)
I worked for 6 years in a private company and was terminated without notice. Am I eligible for gratuity?

# Payslip audit (payslip domain — shows citations)
My basic salary is 18000 and EPF deducted is 1800 per month. Is my EPF deduction correct?

# PF withdrawal (PF domain)
I left my job 3 months ago, unemployed, UAN active, KYC done. Can I withdraw my full PF?

# Tax (tax domain)
I earn 8 lakh per year on old regime. Can I claim 80C deduction for PPF and ELSS?
```

## Training

### Stage 1: Retriever Fine-tuning

```bash
python scripts/finetune_retriever.py
```

Fine-tunes all-MiniLM-L6-v2 on 916 (query, positive, hard_negative) triplets extracted from SFT+DPO data with BM25-mined hard negatives. Triplet loss, margin 0.3, 3 epochs.

### Stage 2: LoRA SFT

```bash
python scripts/train_lora.py
```

Fine-tunes LLaMA 3.1 8B Instruct with LoRA (rank 16, α=32) on 285 examples. 4-bit NF4 quantization, 3 epochs, ~9 minutes on A100.

### Stage 3: DPO Alignment

```bash
python scripts/train_dpo.py
```

Trains DPO on 373 preference pairs with β sweep {0.05, 0.10, 0.20}. Winner: β=0.05 (grounded_clean 0.750, zero fabrication). ~10 min/beta on A100.

### Dataset Generation

```bash
# SFT dataset (requires Groq API key)
python scripts/generate_sft_dataset.py

# DPO preference pairs
python scripts/generate_dpo_dataset.py
```

## Evaluation

### Run all evaluations

```bash
bash scripts/run_all_evals.sh
```

This runs 6 evaluation suites in sequence:
1. Sufficiency Gate (110 examples)
2. Router — keyword baseline vs LLM (66 examples)
3. Slot Extractor — regex baseline vs LLM (45 examples)
4. Retriever — BM25 vs FAISS vs fine-tuned FAISS (20 prompts)
5. Condition Coverage Score (17 reasoning prompts)
6. RAGAS Faithfulness + Answer Relevance (20 prompts)

### Run the 4-config ablation

```bash
python eval/ablation_runner.py 2>&1 | tee data/ablation.log
```

Runs all 20 held-out prompts through 4 system configurations:
- **A: Vanilla RAG** — BM25 + raw LLaMA (grounded_clean: 0.550)
- **B: +Pre-retrieval** — FAISS + router/slots (grounded_clean: 0.800)
- **C: +Reasoner** — B + eligibility reasoner (CCS: 0.631)
- **D: Full system** — C + DPO generator (grounded_clean: 0.700, CCS: 0.647)

### Run DPO evaluation

```bash
python scripts/eval_dpo.py
```

Compares SFT-only vs all 3 DPO betas on 20 held-out prompts.

## Project Structure

```
shramiksaathi/
├── app.py                      # Gradio demo (fully local, no external APIs)
├── PROJECT_PROPOSAL.md         # Full project proposal
│
├── src/
│   ├── pipeline.py             # Full pipeline orchestrator
│   ├── cross_domain_router.py  # Keyword baseline + LLM router
│   ├── slot_extractor.py       # Regex baseline + LLM extractor
│   ├── sufficiency_gate.py     # Rule-based gate
│   ├── react_loop.py           # ReAct with SearchKB/GetPolicy/ParsePayslip
│   ├── eligibility_reasoner.py # Condition Parser + Checker + Gap Resolver
│   ├── search_kb.py            # FAISS search wrapper
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
│   ├── generate_sft_dataset.py
│   ├── train_lora.py           # Stage 2: LoRA SFT
│   ├── generate_dpo_dataset.py
│   ├── train_dpo.py            # Stage 3: DPO with beta sweep
│   ├── eval_dpo.py             # DPO held-out evaluation
│   ├── finetune_retriever.py   # Stage 1: Retriever fine-tuning
│   └── run_all_evals.sh        # Master eval runner
│
├── data/
│   ├── kb.jsonl                # 311 KB documents (4 domains)
│   ├── sft_train.jsonl         # 285 SFT training examples
│   ├── dpo_pairs.jsonl         # 373 DPO preference pairs
│   ├── eval_heldout.jsonl      # 20 held-out evaluation prompts
│   ├── router_eval.jsonl       # 66 router eval examples
│   ├── slot_eval.jsonl         # 45 slot eval examples
│   ├── sufficiency_eval.jsonl  # 110 gate eval examples
│   ├── *_results.json          # All evaluation results
│   └── *.log                   # All evaluation logs
│
├── index/
│   ├── faiss_index.bin              # Original FAISS index
│   ├── faiss_index_finetuned.bin    # Fine-tuned retriever index
│   └── chunk_store.json             # doc_id → text + metadata
│
└── out/                        # Adapter weights (git-ignored)
    ├── lora_v2/                # SFT adapter
    ├── dpo_beta_050/           # DPO winner (β=0.05)
    └── retriever_finetuned/    # Fine-tuned MiniLM
```

## Technology Stack

| Component | Technology |
|---|---|
| Base LLM | LLaMA 3.1 8B Instruct |
| Fine-tuning | LoRA (PEFT) + DPO (TRL) |
| Quantization | 4-bit NF4 (bitsandbytes) |
| Retrieval | FAISS IndexFlatL2 + sentence-transformers |
| Encoder | all-MiniLM-L6-v2 (384-dim, fine-tuned) |
| Pipeline | Custom Python (no LangChain) |
| Demo | Gradio |
| Training compute | Lightning AI A100 80GB |

## Known Limitations

- **PF domain** grounded_clean stuck at 0.40 — large overlapping KB (240 docs) causes retrieval near-misses
- **ReAct loop** occasionally fabricates user facts in reasoning traces — demo uses direct FAISS retrieval instead
- **DPO dataset** underrepresents tax (10/373 pairs) and refusal dimension (53/80 target)
- **One fabrication** persists in Config D (doc_id suffix mutation: `GAZETTE_INTEREST_RATE_2023_24` → `2024_25`)
- **Cross-encoder reranker** from proposal was not implemented

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

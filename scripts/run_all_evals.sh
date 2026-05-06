#!/bin/bash
set -e
cd ~/shramiksaathi
export GROQ_API_KEY=$(grep GROQ_API_KEY .env | cut -d'=' -f2)

echo "=============================================="
echo "  ShramikSaathi — Full Evaluation Suite"
echo "  $(date)"
echo "=============================================="

echo ""
echo "[1/6] Sufficiency Gate Eval..."
python eval/sufficiency_eval_runner.py 2>&1 | tee data/sufficiency_eval.log

echo ""
echo "[2/6] Router Eval (baseline + LLM)..."
python eval/router_eval_runner.py 2>&1 | tee data/router_eval.log

echo ""
echo "[3/6] Slot Extractor Eval (baseline + LLM)..."
python eval/slot_eval_runner.py 2>&1 | tee data/slot_eval.log

echo ""
echo "[4/6] Retriever Eval (BM25 vs FAISS)..."
python eval/retriever_eval_runner.py 2>&1 | tee data/retriever_eval.log

echo ""
echo "[5/6] Condition Coverage Score..."
python eval/condition_coverage_eval.py 2>&1 | tee data/condition_coverage.log

echo ""
echo "[6/6] RAGAS Eval (Faithfulness + Answer Relevance)..."
python eval/ragas_eval_runner.py 2>&1 | tee data/ragas_eval.log

echo ""
echo "=============================================="
echo "  ALL EVALS COMPLETE — $(date)"
echo "=============================================="
echo ""
echo "  Result files:"
echo "    data/sufficiency_eval.log"
echo "    data/router_eval.log"
echo "    data/slot_eval.log"
echo "    data/retriever_eval.log        + data/retriever_eval_results.json"
echo "    data/condition_coverage.log    + data/condition_coverage_results.json"
echo "    data/ragas_eval.log            + data/ragas_eval_results.json"
echo ""
echo "  Pre-existing (from DPO eval):"
echo "    data/dpo_eval_results.json"
echo "    data/dpo_eval_report.md"
echo "    data/eval_heldout_results.json"
echo ""

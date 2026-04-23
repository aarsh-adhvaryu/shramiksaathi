"""
Pipeline Smoke Test — one query through each pipeline, confirm no crashes.

Purpose: before we build evaluation infrastructure, prove that both pipelines
(baseline vanilla RAG + full ShramikSaathi with Groq) actually work end-to-end.
We've never run them before.

Run from D:\\epfo_copilot\\ project root:
    .venv\\Scripts\\activate
    python tests\\test_pipelines_smoke.py

Expected runtime: ~30-60 seconds (3-5 Groq API calls)
"""

import sys
import time
import traceback
from pathlib import Path

# Make src/ imports work when running from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))


def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_baseline_smoke():
    print_section("SMOKE TEST 1: Baseline Pipeline (BM25 + raw LLaMA)")

    from baseline_pipeline import run_baseline

    test_query = "I left my job 3 months ago. My UAN is active and KYC is done. Can I withdraw my full PF?"

    print(f"\nQuery: {test_query}")
    print(f"\nRunning...")

    t0 = time.time()
    try:
        result = run_baseline(test_query)
        elapsed = time.time() - t0

        print(f"\n✓ Baseline completed in {elapsed:.1f}s")
        print(f"\nPassages retrieved: {len(result['passages'])}")
        for p in result['passages'][:3]:
            print(f"  - {p['doc_id']} (score={p.get('score', 0):.2f})")

        response = result['response']
        print(f"\nResponse ({len(response)} chars):")
        print(f"{response[:500]}{'...' if len(response) > 500 else ''}")

        # Quick checks
        checks = {
            "has passages": len(result['passages']) > 0,
            "has response": len(response) > 20,
            "response not error": "[Error:" not in response,
        }
        print("\nChecks:")
        for k, v in checks.items():
            print(f"  {'✓' if v else '✗'} {k}")

        return all(checks.values()), elapsed

    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n✗ Baseline FAILED after {elapsed:.1f}s")
        print(f"\nError: {type(e).__name__}: {e}")
        print("\nStack trace:")
        traceback.print_exc()
        return False, elapsed


def run_main_smoke():
    print_section("SMOKE TEST 2: Main Pipeline (Router + Slots + Gate + ReAct + Reasoner + Groq)")

    from pipeline import run_pipeline

    test_query = "I left my job 3 months ago. My UAN is active and KYC is done. I want to withdraw my full PF."

    print(f"\nQuery: {test_query}")
    print(f"\nRunning (this exercises router, slot extractor, sufficiency gate,")
    print(f"react loop with tools, eligibility reasoner, and final generation)...")

    session = {"slots": {}, "history": [], "turn": 0, "domain": None}

    t0 = time.time()
    try:
        result = run_pipeline(test_query, session)
        elapsed = time.time() - t0

        print(f"\n✓ Pipeline completed in {elapsed:.1f}s")
        print(f"\nDomain: {result.get('domain')}")
        print(f"Decision: {result.get('decision')}")
        print(f"Coverage: {result.get('coverage')}")
        print(f"Slots: { {k:v for k,v in result.get('slots', {}).items() if v is not None} }")

        response = result['response']
        print(f"\nResponse ({len(response)} chars):")
        print(f"{response[:800]}{'...' if len(response) > 800 else ''}")

        # Quick checks
        checks = {
            "domain identified": result.get('domain') in {"pf", "payslip", "labour", "tax"},
            "has response": len(response) > 20,
            "response not error": "[Error:" not in response,
            "not stuck in ASK loop": result.get('decision') != "ASK",
        }
        print("\nChecks:")
        for k, v in checks.items():
            print(f"  {'✓' if v else '✗'} {k}")

        return all(checks.values()), elapsed

    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n✗ Main Pipeline FAILED after {elapsed:.1f}s")
        print(f"\nError: {type(e).__name__}: {e}")
        print("\nStack trace:")
        traceback.print_exc()
        return False, elapsed


def main():
    print("\n" + "#" * 70)
    print("#  ShramikSaathi — Pipeline Smoke Test")
    print("#  Running 1 query through each pipeline to confirm they work")
    print("#" * 70)

    t_start = time.time()
    baseline_ok, baseline_time = run_baseline_smoke()
    main_ok, main_time = run_main_smoke()
    total = time.time() - t_start

    print_section("SUMMARY")
    print(f"\nBaseline pipeline:  {'✓ PASS' if baseline_ok else '✗ FAIL'}  ({baseline_time:.1f}s)")
    print(f"Main pipeline:      {'✓ PASS' if main_ok else '✗ FAIL'}  ({main_time:.1f}s)")
    print(f"\nTotal smoke test runtime: {total:.1f}s")

    if baseline_ok and main_ok:
        print("\n✓ BOTH PIPELINES WORK END-TO-END")
        print("  → Safe to build evaluation infrastructure on top")
        return 0
    else:
        print("\n✗ AT LEAST ONE PIPELINE FAILED")
        print("  → Fix before building eval infrastructure")
        return 1


if __name__ == "__main__":
    sys.exit(main())

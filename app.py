"""
ShramikSaathi — Optimized Fully Local Demo (Merged Model)
3 LLM calls per query: (1) Router+Slots, (2) Batched Reasoner, (3) Generator
Uses merged DPO model — no adapter overhead.
"""

import os, sys, json, re, time
from pathlib import Path

import torch
import gradio as gr
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from sufficiency_gate import check_sufficiency
from search_kb import SearchKB

DOC_ID_RE = re.compile(r'\[([A-Z][A-Z0-9_]+)\]')

kb = SearchKB(
    index_path=str(ROOT / "index" / "faiss_index.bin"),
    store_path=str(ROOT / "index" / "chunk_store.json"),
    model_name="sentence-transformers/all-MiniLM-L6-v2",
)

ALL_KB_DOC_IDS = set()
with open(ROOT / "data" / "kb.jsonl") as f:
    for line in f:
        if line.strip():
            ALL_KB_DOC_IDS.add(json.loads(line)["doc_id"])

MERGED_MODEL = str(ROOT / "out" / "merged_model")

print("[Model] Loading merged ShramikSaathi model...")
t0 = time.time()
bnb = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
)
tokenizer = AutoTokenizer.from_pretrained(MERGED_MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    MERGED_MODEL, quantization_config=bnb, torch_dtype=torch.bfloat16,
    device_map="auto", attn_implementation="sdpa",
)
model.eval()
print("[Model] Loaded in " + str(round(time.time()-t0, 1)) + "s")



def llm_call(messages, max_tokens=200):
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=4096).to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs, max_new_tokens=max_tokens, do_sample=False,
            temperature=None, top_p=None,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen = out[0][inputs["input_ids"].shape[1]:]
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


# ── CALL 1: Combined Router + Slot Extraction ──

ROUTER_SLOTS_PROMPT = """You are a classifier and slot extractor for an Indian worker rights system.

Given the user query, output a JSON object with:
1. "domain": one of ["pf", "payslip", "labour", "tax"]
2. All relevant slots extracted from the query

SLOT SCHEMAS BY DOMAIN:

pf: intent (full_withdrawal/partial_withdrawal/transfer/kyc_issue/tds_query/employer_complaint/pension), employment_status (employed/unemployed/retired), months_unemployed (int), service_years (int), uan_status (active/inactive), kyc_status (complete/incomplete)

payslip: intent (verify_epf/verify_esi/check_deductions/full_audit/check_bonus), basic_salary (int), gross_salary (int), epf_deducted (int), esi_deducted (int), state (string)

labour: intent (gratuity/wrongful_termination/maternity_benefit/overtime_pay/notice_period), employment_years (int), termination_reason (resignation/employer_terminated/retrenched), last_drawn_salary (int), employer_type (private/government/factory)

tax: intent (tds_on_salary/tds_on_pf/hra_exemption/deductions_80c/itr_filing), annual_income (int), tax_regime (old_regime/new_regime), service_years (int), pf_withdrawal_amount (int)

Output ONLY valid compact JSON. No explanation."""


def combined_route_and_extract(query, chat_history=None):
    context = ""
    if chat_history:
        recent = chat_history[-4:]
        parts = []
        for h in recent:
            parts.append(h["role"] + ": " + h["content"])
        context = "\n".join(parts) + "\n\n"

    raw = llm_call([
        {"role": "system", "content": ROUTER_SLOTS_PROMPT},
        {"role": "user", "content": context + "Query: " + query},
    ], max_tokens=300)

    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        data = json.loads(raw)
        domain = data.pop("domain", "pf")
        if domain not in ("pf", "payslip", "labour", "tax"):
            domain = "pf"
        # Keyword fallback for missed intents
        if domain == "labour" and data.get("intent", "general") == "general":
            q = query.lower()
            if "gratuity" in q: data["intent"] = "gratuity"
            elif "terminat" in q or "fired" in q: data["intent"] = "wrongful_termination"
            elif "maternity" in q: data["intent"] = "maternity_benefit"
            elif "overtime" in q: data["intent"] = "overtime_pay"
            elif "notice" in q: data["intent"] = "notice_period"
        if domain == "pf" and data.get("intent", "general") == "general":
            q = query.lower()
            if "withdraw" in q and ("full" in q or "all" in q or "close" in q): data["intent"] = "full_withdrawal"
            elif "partial" in q or "advance" in q: data["intent"] = "partial_withdrawal"
            elif "transfer" in q: data["intent"] = "transfer"
            elif "kyc" in q: data["intent"] = "kyc_issue"
            elif "tds" in q: data["intent"] = "tds_query"
        if domain == "tax" and data.get("intent", "general") == "general":
            q = query.lower()
            if "80c" in q or "ppf" in q or "elss" in q: data["intent"] = "deductions_80c"
            elif "hra" in q: data["intent"] = "hra_exemption"
            elif "tds" in q: data["intent"] = "tds_on_salary"
        return domain, data
    except json.JSONDecodeError:
        return "pf", {"intent": "general"}


# ── CALL 2: Batched Reasoner ──

REASONER_PROMPT = """You are an eligibility condition extractor for Indian worker rights.

Given MULTIPLE passages, extract ALL eligibility conditions as a JSON array.
Each condition: {"field": "slot_name", "operator": "gte/lte/eq/in/not_null", "value": threshold, "mandatory": true/false, "doc_id": "DOC_ID"}

VALID SLOT NAMES: employment_status, months_unemployed, service_years, uan_status, kyc_status, basic_salary, gross_salary, employment_years, termination_reason, last_drawn_salary, annual_income, tax_regime, pf_withdrawal_amount

RULES:
- Output ONLY a JSON array, no explanation
- Maximum 8 conditions total across all passages
- Mark TDS/warning conditions as mandatory: false
- Use exact field names from the list above"""

RELATED_DOMAINS = {
    "pf": ["pf", "tax"], "tax": ["tax", "pf"],
    "payslip": ["payslip", "pf"], "labour": ["labour"],
}

REASONING_INTENTS = {
    "full_withdrawal", "partial_withdrawal", "transfer", "tds_query", "kyc_issue",
    "verify_epf", "verify_esi", "check_deductions", "check_minimum_wage", "full_audit",
    "gratuity", "wrongful_termination", "maternity_benefit", "overtime_pay",
    "tds_on_salary", "tds_on_pf", "hra_exemption", "deductions_80c",
}

VALUE_ALIASES = {
    "verified": "complete", "approved": "complete", "done": "complete",
    "not_complete": "incomplete", "pending": "incomplete",
    "activated": "active", "enabled": "active",
    "terminated": "employer_terminated", "fired": "employer_terminated",
    "resigned": "resignation", "quit": "resignation",
    "old": "old_regime", "new": "new_regime",
}


def normalize(val):
    s = str(val).lower().strip()
    return VALUE_ALIASES.get(s, s)


def evaluate_condition(slot_val, operator, threshold):
    try:
        if operator == "gte": return float(slot_val) >= float(threshold)
        if operator == "lte": return float(slot_val) <= float(threshold)
        if operator == "gt": return float(slot_val) > float(threshold)
        if operator == "lt": return float(slot_val) < float(threshold)
        if operator == "eq": return normalize(slot_val) == normalize(threshold)
        if operator == "in": return normalize(slot_val) in [normalize(v) for v in threshold]
        if operator == "not_null": return slot_val is not None
    except (ValueError, TypeError):
        return False
    return False


def batched_reasoner(passages, slots, domain, intent):
    allowed = RELATED_DOMAINS.get(domain, [domain])
    relevant = [p for p in passages if p.get("domain", "general") in allowed or p.get("domain") == "general"]
    if not relevant:
        relevant = passages[:3]

    passage_text = ""
    for i, p in enumerate(relevant[:5]):
        did = p.get("doc_id", "?")
        content = p.get("content", "")[:400]
        passage_text += "\n[" + did + "]\n" + content + "\n"

    raw = llm_call([
        {"role": "system", "content": REASONER_PROMPT},
        {"role": "user", "content": "Domain: " + domain + "\nIntent: " + intent + "\n\nPASSAGES:" + passage_text},
    ], max_tokens=300)

    raw = re.sub(r"```json|```", "", raw).strip()
    conditions = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            conditions = [c for c in parsed if isinstance(c, dict) and "field" in c]
    except json.JSONDecodeError:
        pass

    met, failed, warnings, unresolved = [], [], [], []
    for c in conditions:
        field = c.get("field", "")
        slot_val = slots.get(field)
        mandatory = c.get("mandatory", True)

        if slot_val is None:
            if mandatory:
                unresolved.append(c)
            continue

        result = evaluate_condition(slot_val, c.get("operator", "eq"), c.get("value"))
        c["slot_value"] = slot_val
        if not mandatory:
            warnings.append(c)
        elif result:
            met.append(c)
        else:
            failed.append(c)

    total = len(met) + len(failed) + len(unresolved)
    resolved = len(met) + len(failed)
    coverage = round(resolved / total, 2) if total > 0 else 1.0

    if failed:
        decision, eligible = "ANSWER", False
    elif unresolved:
        decision, eligible = "ASK", None
    elif not conditions:
        decision, eligible = "ANSWER", True
    else:
        decision, eligible = "ANSWER", True

    question = None
    if decision == "ASK" and unresolved:
        field = unresolved[0].get("field", "unknown")
        questions = {
            "employment_status": "Are you currently employed, unemployed, or retired?",
            "service_years": "How many total years have you contributed to PF?",
            "months_unemployed": "How many months have you been unemployed?",
            "uan_status": "Is your UAN currently active?",
            "kyc_status": "Is your KYC complete on the EPFO portal?",
            "employment_years": "How many years have you worked with this employer?",
            "termination_reason": "Did you resign, were you fired, or retrenched?",
            "annual_income": "What is your total annual income?",
            "tax_regime": "Are you on the old or new tax regime?",
        }
        question = questions.get(field, "Could you provide your " + field.replace("_", " ") + "?")

    return {
        "decision": decision, "eligible": eligible, "coverage": coverage,
        "met": met, "failed": failed, "warnings": warnings, "unresolved": unresolved,
        "question": question,
    }


# ── CALL 3: Generator ──

GENERATOR_PROMPT = """You are ShramikSaathi, an Indian worker rights support copilot.
You help workers with PF/EPFO, payslip audit, labour rights, and income tax queries.

RULES:
- Every factual claim must cite its doc_id in brackets e.g. [GRATUITY_ACT_S4_ELIG]
- Only cite doc_ids from the RETRIEVED PASSAGES section
- Never invent doc_ids
- Keep answers structured: result first, then steps, then warnings
- Use simple language"""

INTENT_SUBDOMAINS = {
    "full_withdrawal": ["withdrawal"], "partial_withdrawal": ["withdrawal"],
    "transfer": ["transfer"], "kyc_issue": ["kyc", "uan"],
    "tds_query": ["taxation"], "employer_complaint": ["employer", "grievance"],
    "verify_epf": ["epf_deduction", "tool_output"], "verify_esi": ["esi_deduction", "tool_output"],
    "check_deductions": ["professional_tax", "epf_deduction", "esi_deduction", "tool_output"],
    "full_audit": ["epf_deduction", "esi_deduction", "professional_tax", "wage_structure", "tool_output"],
    "gratuity": ["gratuity"], "wrongful_termination": ["termination"],
    "maternity_benefit": ["maternity"], "overtime_pay": ["overtime"],
    "notice_period": ["termination"],
    "tds_on_salary": ["tds_salary"], "tds_on_pf": ["tds_pf"],
    "hra_exemption": ["hra"], "deductions_80c": ["deductions"],
}


def build_generator_input(query, domain, passages, reasoning, slots):
    passages_text = kb.format_for_prompt(passages)
    reasoning_text = ""
    if reasoning:
        lines = ["ELIGIBILITY REASONING TRACE:",
                 "  Decision: " + str(reasoning.get("decision", ""))]
        if reasoning.get("eligible") is not None:
            lines.append("  Eligible: " + str(reasoning["eligible"]))
        lines.append("  Coverage: " + str(reasoning.get("coverage", 0)))
        for c in reasoning.get("met", []):
            lines.append("    V " + c.get("field", "?") + " " + c.get("operator", "?") + " " + str(c.get("value", "?")) + " [" + c.get("doc_id", "?") + "]")
        for c in reasoning.get("failed", []):
            lines.append("    X " + c.get("field", "?") + " " + c.get("operator", "?") + " " + str(c.get("value", "?")) + " [" + c.get("doc_id", "?") + "]")
        for c in reasoning.get("warnings", []):
            lines.append("    ! " + c.get("field", "?") + " " + c.get("operator", "?") + " " + str(c.get("value", "?")) + " [" + c.get("doc_id", "?") + "]")
        for c in reasoning.get("unresolved", []):
            lines.append("    ? " + c.get("field", "?") + " -- slot missing")
        reasoning_text = "\n".join(lines)
    filled = {k: v for k, v in slots.items() if v is not None}
    return ("USER QUERY:\n" + query + "\n\nDOMAIN: " + domain
            + "\n\nRETRIEVED PASSAGES:\n" + passages_text
            + "\n\n" + reasoning_text
            + "\n\nSLOTS FILLED:\n" + json.dumps(filled, indent=2)
            + "\n\nProduce the final answer now.")


def score_response(response, retrieved_doc_ids):
    cited = set(DOC_ID_RE.findall(response))
    fabricated = cited - ALL_KB_DOC_IDS
    grounded = cited.intersection(set(retrieved_doc_ids))
    return {
        "total_citations": len(cited),
        "grounded_citations": len(grounded),
        "fabricated_citations": len(fabricated),
        "cited_doc_ids": sorted(cited),
        "fabricated_doc_ids": sorted(fabricated),
        "fabrication_free": len(fabricated) == 0,
    }



def strip_fabricated_citations(response, retrieved_doc_ids):
    """Remove any cited [DOC_ID] not in retrieved passages or KB."""
    valid = set(retrieved_doc_ids) | ALL_KB_DOC_IDS
    def replacer(match):
        doc_id = match.group(1)
        if doc_id in valid:
            return match.group(0)
        return ""  # strip fabricated citation
    return DOC_ID_RE.sub(replacer, response).strip()


def merge_slots(old, new):
    merged = dict(old)
    for k, v in new.items():
        if v is not None:
            merged[k] = v
    return merged


def run_query(user_query, session_state):
    if session_state is None:
        session_state = {"slots": {}, "history": [], "turn": 0, "domain": None}

    history = session_state.get("history", [])[-10:]
    slots = session_state.get("slots", {})
    domain = session_state.get("domain", None)
    turn = session_state.get("turn", 0) + 1
    total_start = time.time()
    trace = []

    # CALL 1: Combined Router + Slots (~5-10s)
    t0 = time.time()
    new_domain, new_slots = combined_route_and_extract(user_query, history)
    dt1 = time.time() - t0

    if domain is not None and new_domain != domain:
        slots = {}
    domain = new_domain
    slots = merge_slots(slots, new_slots)
    intent = slots.get("intent", "general")
    filled = {k: v for k, v in slots.items() if v is not None}

    trace.append("### Call 1: Router + Slots (" + str(round(dt1, 1)) + "s)")
    trace.append("**Domain:** " + domain + " | **Intent:** " + intent + " | **Slots:** " + str(len(filled)))
    if filled:
        trace.append("```")
        for k, v in filled.items():
            trace.append("  " + k + ": " + str(v))
        trace.append("```")

    # Sufficiency Gate (instant)
    gate = check_sufficiency(slots, domain)
    trace.append("\n### Sufficiency Gate")
    if not gate["sufficient"]:
        question = gate["question"]
        trace.append("**BLOCKED** | Missing: " + str(gate["missing"]))
        history.append({"role": "user", "content": user_query})
        history.append({"role": "assistant", "content": question})
        state = {"slots": slots, "history": history, "turn": turn, "domain": domain}
        return question, state, "\n".join(trace), "**Gate blocked** -- collecting more info."
    trace.append("**PASSED**")

    # FAISS Retrieval with domain filtering
    t0 = time.time()
    raw_passages = kb.search(user_query, top_k=10)
    domain_hits = [p for p in raw_passages if p.get("domain") == domain]
    other_hits = [p for p in raw_passages if p.get("domain") != domain]
    passages = (domain_hits + other_hits)[:5]
    if len(domain_hits) < 2:
        # Retry with domain-specific query boost
        boosted = kb.search(domain + " " + user_query, top_k=5)
        boosted_domain = [p for p in boosted if p.get("domain") == domain]
        seen = {p.get("doc_id") for p in passages}
        for p in boosted_domain:
            if p.get("doc_id") not in seen and len(passages) < 5:
                passages.insert(len(domain_hits), p)
                seen.add(p.get("doc_id"))
    doc_ids = [p.get("doc_id", "?") for p in passages]
    trace.append("\n### FAISS Retrieval (" + str(round(time.time()-t0, 2)) + "s)")
    trace.append("Doc IDs: " + ", ".join(doc_ids))

    # CALL 2: Batched Reasoner (~10-15s)
    reasoning = None
    cov = 0.0
    if intent in REASONING_INTENTS:
        t0 = time.time()
        reasoning = batched_reasoner(passages, slots, domain, intent)
        dt2 = time.time() - t0
        cov = reasoning.get("coverage", 0.0)
        trace.append("\n### Call 2: Batched Reasoner (" + str(round(dt2, 1)) + "s)")
        trace.append("**Decision:** " + reasoning["decision"] + " | **Coverage:** " + str(cov))
        trace.append("Met: " + str(len(reasoning["met"])) + " | Failed: " + str(len(reasoning["failed"])) + " | Unresolved: " + str(len(reasoning["unresolved"])))

        if reasoning["decision"] == "ASK":
            question = reasoning["question"]
            history.append({"role": "user", "content": user_query})
            history.append({"role": "assistant", "content": question})
            state = {"slots": slots, "history": history, "turn": turn, "domain": domain}
            return question, state, "\n".join(trace), "**Needs more info** | Coverage: " + str(cov)
    else:
        trace.append("\n### Reasoner: *Skipped (informational)*")

    # CALL 3: Generator (~15-25s)
    t0 = time.time()
    user_content = build_generator_input(user_query, domain, passages, reasoning, slots)
    answer = llm_call([
        {"role": "system", "content": GENERATOR_PROMPT},
        {"role": "user", "content": user_content},
    ], max_tokens=500)
    dt3 = time.time() - t0
    trace.append("\n### Call 3: Generator (" + str(round(dt3, 1)) + "s)")

    total_time = time.time() - total_start
    trace.append("\n**Total: " + str(round(total_time, 1)) + "s**")

    answer = strip_fabricated_citations(answer, doc_ids)
    scores = score_response(answer, doc_ids)
    history.append({"role": "user", "content": user_query})
    history.append({"role": "assistant", "content": answer})
    state = {"slots": slots, "history": history, "turn": turn, "domain": domain}

    fab_status = "Yes" if scores["fabrication_free"] else "NO -- " + str(scores["fabricated_doc_ids"])
    eval_parts = [
        "### Live Evaluation\n",
        "| Metric | Value |",
        "|--------|-------|",
        "| Domain | " + domain + " |",
        "| Intent | " + intent + " |",
        "| Slots | " + str(len(filled)) + " |",
        "| Passages | " + str(len(passages)) + " |",
        "| Condition Coverage | " + str(round(cov, 2)) + " |",
        "| Citations | " + str(scores["total_citations"]) + " |",
        "| Grounded | " + str(scores["grounded_citations"]) + " |",
        "| Fabricated | " + str(scores["fabricated_citations"]) + " |",
        "| Fabrication Free | " + fab_status + " |",
        "| Total Time | " + str(round(total_time, 1)) + "s |",
        "",
        "**Cited:** " + (", ".join(scores["cited_doc_ids"]) if scores["cited_doc_ids"] else "None"),
    ]
    if reasoning and reasoning.get("decision"):
        eval_parts.append("\n**Reasoner:** " + reasoning["decision"])
        if reasoning.get("eligible") is not None:
            eval_parts.append("**Eligible:** " + str(reasoning["eligible"]))

    return answer, state, "\n".join(trace), "\n".join(eval_parts)


with gr.Blocks() as demo:
    gr.Markdown("# ShramikSaathi -- Indian Worker Rights Copilot")
    gr.Markdown("**Domains:** PF/EPFO | Payslip Audit | Labour Rights | Income Tax")
    gr.Markdown("*One model, 3 LLM calls per query: LLaMA 3.1 8B + DPO | Fully local*")

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(height=500, label="Conversation")
            session_state = gr.State(None)
            with gr.Row():
                msg = gr.Textbox(
                    placeholder="Ask about PF, payslip, gratuity, TDS...",
                    label="Your question", scale=5, lines=2,
                )
                send_btn = gr.Button("Send", variant="primary", scale=1)
            clear_btn = gr.Button("Reset Session")

        with gr.Column(scale=1):
            with gr.Tab("Evaluation"):
                eval_display = gr.Markdown(value="*Send a query to see live evaluation...*")
            with gr.Tab("Pipeline Trace"):
                trace_display = gr.Markdown(value="*Send a query to see pipeline trace...*")

    gr.Markdown("""
### Example Queries
- I worked for 6 years in a private company, terminated without notice. Am I eligible for gratuity?
- My basic salary is 20000, EPF deducted is 1200. Is this correct?
- I left my job 3 months ago, unemployed, UAN active, KYC done. Can I withdraw PF?
- I earn 8 lakh per year on old regime. Can I claim 80C deduction?
    """)

    def respond(user_msg, chat_history, state):
        if not user_msg.strip():
            return "", chat_history or [], state, "", ""
        answer, new_state, trace, eval_md = run_query(user_msg, state)
        updated = (chat_history or []) + [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": answer},
        ]
        return "", updated, new_state, eval_md, trace

    def reset():
        return [], None, "*Send a query to see live evaluation...*", "*Send a query to see pipeline trace...*"

    msg.submit(respond, [msg, chatbot, session_state], [msg, chatbot, session_state, eval_display, trace_display])
    send_btn.click(respond, [msg, chatbot, session_state], [msg, chatbot, session_state, eval_display, trace_display])
    clear_btn.click(reset, [], [chatbot, session_state, eval_display, trace_display])

demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
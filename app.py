"""
ShramikSaathi — Gradio Demo
Pipeline: Groq (router/slots/ReAct) + Local DPO model (generator)
"""

import os, sys, json, time
from pathlib import Path
from dotenv import load_dotenv

import torch
import gradio as gr
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from cross_domain_router import llm_route
from slot_extractor import extract_slots, merge_slots
from sufficiency_gate import check_sufficiency
from eligibility_reasoner import run_eligibility_reasoner
from react_loop import react_retrieve
from search_kb import SearchKB

# ── Load KB ────────────────────────────────────────────────────────────────
kb = SearchKB(
    index_path=str(ROOT / "index" / "faiss_index.bin"),
    store_path=str(ROOT / "index" / "chunk_store.json"),
)

# ── Load local DPO model ──────────────────────────────────────────────────
MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
DPO_ADAPTER = str(ROOT / "out" / "dpo_beta_050")

print("[Model] Loading LLaMA 3.1 8B + DPO adapter...")
t0 = time.time()
bnb = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
)
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, quantization_config=bnb, torch_dtype=torch.bfloat16,
    device_map="auto", attn_implementation="sdpa",
)
model = PeftModel.from_pretrained(base_model, DPO_ADAPTER)
model.eval()
print(f"[Model] Loaded in {time.time()-t0:.1f}s | VRAM {torch.cuda.memory_allocated()/1e9:.2f}GB")


# ── Generator prompt ──────────────────────────────────────────────────────
GENERATOR_PROMPT = """You are ShramikSaathi, an Indian worker rights support copilot.
You help workers with PF/EPFO, payslip audit, labour rights, and income tax queries.

You will be given:
1. The user's query
2. The detected domain
3. Retrieved KB passages with doc_ids and dates
4. An eligibility reasoning trace (if applicable)
5. Filled slots

Your job: produce a clear, cited, structured answer.

RULES:
- Every factual claim must cite its doc_id in brackets e.g. [GRATUITY_ACT_S4_ELIG]
- CITATION RULE: Only cite doc_ids that appear verbatim in the RETRIEVED PASSAGES section.
  Never invent new doc_ids, suffixes, or section numbers.
- If eligibility reasoning is provided, include the condition trace in your answer
- If decision is ANSWER + eligible=True  → confirm eligibility, give next steps
- If decision is ANSWER + eligible=False → clearly state not eligible, explain why
- If decision is ESCALATE → say KB lacks info, suggest appropriate grievance portal
- Keep answers structured: result first, then steps, then warnings/caveats
- Never make up information not in the passages
- Use simple language — the user may not know legal terminology"""

# Intent → subdomain mapping (from pipeline.py)
INTENT_SUBDOMAINS = {
    "full_withdrawal": ["withdrawal"], "partial_withdrawal": ["withdrawal"],
    "transfer": ["transfer"], "kyc_issue": ["kyc", "uan"],
    "tds_query": ["taxation"], "employer_complaint": ["employer", "grievance"],
    "pension": ["pension"], "nomination_update": ["nomination"],
    "verify_epf": ["epf_deduction", "tool_output"],
    "verify_esi": ["esi_deduction", "tool_output"],
    "check_deductions": ["professional_tax", "epf_deduction", "esi_deduction", "tool_output"],
    "check_minimum_wage": ["minimum_wage"],
    "full_audit": ["epf_deduction", "esi_deduction", "professional_tax", "wage_structure", "tool_output"],
    "check_bonus": ["bonuses"],
    "gratuity": ["gratuity"], "wrongful_termination": ["termination"],
    "maternity_benefit": ["maternity"], "overtime_pay": ["overtime"],
    "notice_period": ["termination"],
    "tds_on_salary": ["tds_salary"], "tds_on_pf": ["tds_pf"],
    "hra_exemption": ["hra"], "deductions_80c": ["deductions"],
    "refund_status": ["refund"], "form16": ["tds_salary"],
    "itr_filing": ["tds_salary", "deductions"],
}

REASONING_INTENTS = {
    "full_withdrawal", "partial_withdrawal", "transfer", "tds_query", "kyc_issue",
    "verify_epf", "verify_esi", "check_deductions", "check_minimum_wage", "full_audit",
    "gratuity", "wrongful_termination", "maternity_benefit", "overtime_pay",
    "tds_on_salary", "tds_on_pf", "hra_exemption", "deductions_80c",
}


def filter_passages_for_reasoner(passages, intent):
    subs = INTENT_SUBDOMAINS.get(intent)
    if not subs:
        return passages
    filtered = [p for p in passages if p.get("subdomain", "") in subs]
    return filtered if filtered else passages


def build_generator_input(query, domain, passages, reasoning, slots):
    passages_text = kb.format_for_prompt(passages)
    reasoning_text = ""
    if reasoning:
        lines = [
            "ELIGIBILITY REASONING TRACE:",
            f"  Decision: {reasoning.get('decision', '')}",
        ]
        if reasoning.get("eligible") is not None:
            lines.append(f"  Eligible: {reasoning['eligible']}")
        lines.append(f"  Coverage: {reasoning.get('coverage', 0)}")
        for c in reasoning.get("met", []):
            lines.append(f"    ✓ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id','?')}]")
        for c in reasoning.get("failed", []):
            lines.append(f"    ✗ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id','?')}]")
        for c in reasoning.get("warnings", []):
            lines.append(f"    ⚠ {c.get('field','?')} {c.get('operator','?')} {c.get('value','?')} [{c.get('doc_id','?')}]")
        for c in reasoning.get("unresolved", []):
            lines.append(f"    ? {c.get('field','?')} — slot missing")
        reasoning_text = "\n".join(lines)

    filled = {k: v for k, v in slots.items() if v is not None}
    return f"""USER QUERY:
{query}

DOMAIN: {domain}

RETRIEVED PASSAGES:
{passages_text}

{reasoning_text}

SLOTS FILLED:
{json.dumps(filled, indent=2)}

Produce the final answer now."""


def local_generate(system_prompt, user_content):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=3072).to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs, max_new_tokens=600, do_sample=False,
            temperature=None, top_p=None,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen = out[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


# ── Session state ─────────────────────────────────────────────────────────
sessions = {}


def get_session(session_id):
    if session_id not in sessions:
        sessions[session_id] = {"slots": {}, "history": [], "turn": 0, "domain": None}
    return sessions[session_id]


def run_query(user_query, chat_history, session_state):
    """Full pipeline: Groq pre-retrieval + local DPO generator."""
    if session_state is None:
        session_state = {"slots": {}, "history": [], "turn": 0, "domain": None}

    history = session_state.get("history", [])
    slots = session_state.get("slots", {})
    domain = session_state.get("domain", None)
    turn = session_state.get("turn", 0) + 1

    meta_lines = []

    # Step 1: Router (Groq)
    router_result = llm_route(user_query)
    new_domain = router_result["domain"]
    confidence = router_result["confidence"]

    if domain is not None and new_domain != domain:
        slots = {}
        meta_lines.append(f"Domain switch: {domain} → {new_domain}")

    domain = new_domain
    meta_lines.append(f"Router → {domain} (conf={confidence})")

    # Step 2: Slot Extraction (Groq)
    new_slots = extract_slots(user_query, domain, chat_history=history)
    slots = merge_slots(slots, new_slots)
    intent = slots.get("intent", "general")
    filled = {k: v for k, v in slots.items() if v is not None}
    meta_lines.append(f"Intent: {intent} | Slots: {filled}")

    # Step 3: Sufficiency Gate
    gate = check_sufficiency(slots, domain)
    if not gate["sufficient"]:
        question = gate["question"]
        meta_lines.append(f"Gate blocked — missing: {gate['missing']}")
        history.append({"role": "user", "content": user_query})
        history.append({"role": "assistant", "content": question})
        state = {"slots": slots, "history": history, "turn": turn, "domain": domain}
        meta_text = "\n".join(meta_lines)
        return question, chat_history + [[user_query, question]], state, meta_text

    # Step 4: ReAct Retrieval (Groq)
    meta_lines.append("Gate passed — retrieving...")
    passages = react_retrieve(user_query, domain, intent, slots, kb)
    doc_ids = [p.get("doc_id", "?") for p in passages]
    meta_lines.append(f"Retrieved {len(passages)} passages: {doc_ids}")

    # Step 5: Eligibility Reasoner (Groq)
    reasoning = None
    if intent in REASONING_INTENTS:
        reasoner_passages = filter_passages_for_reasoner(passages, intent)
        reasoning = run_eligibility_reasoner(reasoner_passages, slots, domain=domain)
        meta_lines.append(f"Reasoner → {reasoning['decision']} | Coverage: {reasoning['coverage']}")

        if reasoning["decision"] == "ASK":
            question = reasoning["question"]
            history.append({"role": "user", "content": user_query})
            history.append({"role": "assistant", "content": question})
            state = {"slots": slots, "history": history, "turn": turn, "domain": domain}
            meta_text = "\n".join(meta_lines)
            return question, chat_history + [[user_query, question]], state, meta_text

    # Step 6: Generate (LOCAL DPO MODEL)
    meta_lines.append("Generating with local DPO model...")
    user_content = build_generator_input(user_query, domain, passages, reasoning, slots)
    t0 = time.time()
    answer = local_generate(GENERATOR_PROMPT, user_content)
    gen_time = time.time() - t0
    meta_lines.append(f"Generated in {gen_time:.1f}s")

    history.append({"role": "user", "content": user_query})
    history.append({"role": "assistant", "content": answer})

    state = {"slots": slots, "history": history, "turn": turn, "domain": domain}
    meta_text = "\n".join(meta_lines)
    return answer, chat_history + [[user_query, answer]], state, meta_text


# ── Gradio UI ─────────────────────────────────────────────────────────────

with gr.Blocks(
    title="ShramikSaathi — Indian Worker Rights Copilot",
    theme=gr.themes.Soft(),
) as demo:
    gr.Markdown("""
# ShramikSaathi — Indian Worker Rights Copilot
**Domains:** PF/EPFO • Payslip Audit • Labour Rights • Income Tax

Ask any question about your PF withdrawal, payslip deductions, gratuity, TDS, or labour rights.
The system extracts your context, verifies eligibility conditions, and gives a cited answer.

*Generator: LLaMA 3.1 8B + DPO (local) | Pre-retrieval: Groq LLaMA 3.1 8B*
    """)

    chatbot = gr.Chatbot(height=500, label="Conversation")
    session_state = gr.State(None)

    with gr.Row():
        msg = gr.Textbox(
            placeholder="e.g. I left my job 3 months ago, UAN active, KYC done. Can I withdraw my PF?",
            label="Your question", scale=5, lines=2,
        )
        send_btn = gr.Button("Send", variant="primary", scale=1)

    with gr.Accordion("Pipeline Debug Info", open=False):
        meta_display = gr.Textbox(label="Pipeline trace", lines=8, interactive=False)

    with gr.Row():
        clear_btn = gr.Button("Reset Session")
        examples_btn = gr.Button("Show Examples")

    def respond(user_msg, chat_history, state):
        if not user_msg.strip():
            return "", chat_history or [], state, ""
        answer, updated_history, new_state, meta = run_query(
            user_msg, chat_history or [], state
        )
        return "", updated_history, new_state, meta

    def reset():
        return [], None, ""

    def show_examples():
        examples = [
            "I left my job 3 months ago. My UAN is active and KYC is done. I want to withdraw my full PF balance.",
            "My basic salary is 20000, EPF deducted is 1200. Is this correct?",
            "I worked for 6 years and was terminated without notice. Am I eligible for gratuity?",
            "I earn 8 lakh per year. Can I claim 80C deduction for PPF and ELSS?",
        ]
        return "\n\n".join(f"**Example {i+1}:** {e}" for i, e in enumerate(examples))

    msg.submit(respond, [msg, chatbot, session_state], [msg, chatbot, session_state, meta_display])
    send_btn.click(respond, [msg, chatbot, session_state], [msg, chatbot, session_state, meta_display])
    clear_btn.click(reset, [], [chatbot, session_state, meta_display])

demo.launch(server_name="0.0.0.0", server_port=7860, share=True)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_plan.py (Claude Code version)

Goal:
- Input: a PDF paper file (mechanistic interpretability / alignment / etc.)
- Output:
  1) plan.md (concise; ONLY Objective/Hypothesis/Methodology/Experiments; NO evidence/unknowns)
  2) plan_with_evidence.md (includes evidence + unknowns; still structured)

Usage:
  python generate_plan.py --file_path data/12_Why_Cannot_Transformers_Learn_Multiplication-Reverse-Engineering_Reveals_Long-Range_Dependency_Pitfalls.pdf --out_dir experiments_human_repo/12_Why_Cannot_Transformers_Learn_Multiplication-Reverse-Engineering_Reveals_Long-Range_Dependency_Pitfalls

Optional:
  python generate_plan.py --file_path paper.pdf --out_dir ./outputs --claude_cmd claude
  python generate_plan.py --file_path paper.pdf --out_dir ./outputs --max_words 280
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional


# ---------------------------
# Claude invocation
# ---------------------------
def run_claude(
    claude_cmd: str,
    prompt: str,
    timeout_s: int = 1800,
) -> str:
    """
    Run Claude Code CLI with the given prompt via stdin.
    Captures stdout as the model output.

    Note:
    - Different Claude CLI versions may support different flags. This implementation
      uses the simplest universally available pattern: send prompt via stdin.
    - If your Claude CLI requires extra flags, pass them via --claude_cmd as a string,
      e.g. --claude_cmd "claude --dangerously-allow-file-access" (if applicable in your setup).
    """
    # Allow claude_cmd to include extra args; split safely.
    cmd_parts = split_shell_like(claude_cmd)

    proc = subprocess.run(
        cmd_parts,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Claude CLI failed.\n"
            f"Command: {claude_cmd}\n"
            f"Return code: {proc.returncode}\n"
            f"STDERR:\n{proc.stderr.strip()}\n"
            f"STDOUT:\n{proc.stdout.strip()}\n"
        )
    return proc.stdout.strip()


def split_shell_like(s: str) -> List[str]:
    """
    Minimal shell-like splitting (handles quoted substrings).
    Avoids requiring shlex edge-cases; good enough for typical commands.
    """
    import shlex
    return shlex.split(s)


# ---------------------------
# JSON parsing helpers
# ---------------------------
def parse_json_strict(text: str) -> Dict[str, Any]:
    """
    Parse JSON output. If wrapped in code fences, strip them.
    """
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n", "", t)
        t = re.sub(r"\n```$", "", t).strip()
    return json.loads(t)


def normalize_unknown(x: Any) -> str:
    """
    Normalize unknown-ish values to "Unknown".
    """
    if x is None:
        return "Unknown"
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return "Unknown"
        if s.lower() in {"unknown", "n/a", "na", "not specified", "not stated"}:
            return "Unknown"
        return s
    return str(x)


# ---------------------------
# Prompting
# ---------------------------
def build_plan_prompt(pdf_path: str, max_words: int) -> str:
    """
    Ask Claude to read the PDF directly from local path and output a JSON plan.
    We request evidence + unknowns in the JSON; we'll render two markdown files later.
    """
    schema = {
        "objective": {
            "text": "string|Unknown",
            "evidence": [{"page": "int", "quote": "string"}]
        },
        "hypothesis": {
            "items": [
                {"text": "string", "evidence": [{"page": "int", "quote": "string"}]}
            ],
            "Unknown_if_missing": True
        },
        "methodology": {
            "items": [
                {"text": "string", "evidence": [{"page": "int", "quote": "string"}]}
            ],
            "Unknown_if_missing": True
        },
        "experiments": {
            "items": [
                {
                    "name": "string",
                    "what_varied": "string|Unknown",
                    "metric": "string|Unknown",
                    "main_result": "string|Unknown",
                    "evidence": [{"page": "int", "quote": "string"}]
                }
            ],
            "Unknown_if_missing": True
        },
        "unknowns": ["string"]
    }

    # The concise plan.md will be rendered to contain ONLY the four sections, no evidence/unknowns.
    # This prompt enforces: if missing => Unknown, and we keep methodology non-trivial.
    prompt = f"""
You are generating a structured Plan for a mechanistic interpretability paper to be evaluated by a standardized pipeline.

You MUST read the PDF directly from this local path:
{pdf_path}

Hard constraints:
1) ONLY use information from the PDF. Do NOT use external knowledge.
2) Output MUST be valid JSON ONLY. No markdown, no commentary.
3) The final plan must be concise:
   - Keep the combined length of objective+hypothesis+methodology+experiments summaries within ~{max_words} words.
   - Methodology must not be empty or too shallow: include the core approach, model/data setting if stated, key analysis/intervention techniques, and how claims are tested.
4) The output must have EXACTLY these four content sections:
   - objective
   - hypothesis
   - methodology
   - experiments
   If a section cannot be found from the PDF, set it explicitly to "Unknown" (or empty items with Unknown_if_missing honored).
5) Evidence:
   - For each hypothesis/methodology item and each experiment entry, include at least one evidence quote with page number.
   - Quotes must be short (<= 35 words) and plausibly verbatim from the PDF.
6) Experiments must be a separate section (NOT nested under methodology). Provide 2-6 experiments if present, else Unknown.
7) Add an "unknowns" list for important missing details that a reproducer/evaluator would want but the PDF does not specify.

Required JSON schema (types + keys). Follow it strictly:
{json.dumps(schema, indent=2)}

Now produce the JSON.
""".strip()
    return prompt


# ---------------------------
# Rendering: two markdown outputs
# ---------------------------
def render_plan_md_concise(plan: Dict[str, Any]) -> str:
    """
    Concise plan.md:
    - Only Objective / Hypothesis / Methodology / Experiments
    - No evidence
    - No unknowns section
    """
    obj = extract_objective_text(plan)
    hyp = extract_list_text(plan, "hypothesis")
    meth = extract_list_text(plan, "methodology")
    exps = extract_experiments_text(plan, include_evidence=False)

    md = []
    md.append("# Plan\n")
    md.append("## Objective\n")
    md.append(f"{obj}\n\n")

    md.append("## Hypothesis\n")
    md.append(f"{hyp}\n\n")

    md.append("## Methodology\n")
    md.append(f"{meth}\n\n")

    md.append("## Experiments\n")
    md.append(f"{exps}\n")

    return "".join(md)


def render_plan_md_with_evidence(plan: Dict[str, Any]) -> str:
    """
    plan_with_evidence.md:
    - Same four sections
    - Include evidence under each item
    - Include Unknowns section
    """
    obj_text, obj_ev = extract_objective_with_evidence(plan)
    hyp_text = extract_list_text(plan, "hypothesis")
    hyp_ev_lines = extract_list_evidence_lines(plan, "hypothesis")

    meth_text = extract_list_text(plan, "methodology")
    meth_ev_lines = extract_list_evidence_lines(plan, "methodology")

    exps_text = extract_experiments_text(plan, include_evidence=True)
    unknowns = plan.get("unknowns", [])
    if not isinstance(unknowns, list):
        unknowns = []

    md = []
    md.append("# Plan (with evidence)\n")

    md.append("## Objective\n")
    md.append(f"{obj_text}\n")
    if obj_ev:
        md.append("\n**Evidence**:\n")
        for ln in obj_ev:
            md.append(f"- {ln}\n")
    md.append("\n")

    md.append("## Hypothesis\n")
    md.append(f"{hyp_text}\n")
    if hyp_ev_lines:
        md.append("\n**Evidence**:\n")
        for ln in hyp_ev_lines:
            md.append(f"- {ln}\n")
    md.append("\n")

    md.append("## Methodology\n")
    md.append(f"{meth_text}\n")
    if meth_ev_lines:
        md.append("\n**Evidence**:\n")
        for ln in meth_ev_lines:
            md.append(f"- {ln}\n")
    md.append("\n")

    md.append("## Experiments\n")
    md.append(f"{exps_text}\n")

    md.append("\n## Unknowns\n")
    if unknowns:
        for u in unknowns:
            md.append(f"- {normalize_unknown(u)}\n")
    else:
        md.append("- (none)\n")

    return "".join(md)


def extract_objective_text(plan: Dict[str, Any]) -> str:
    obj = plan.get("objective", {})
    if isinstance(obj, dict):
        return normalize_unknown(obj.get("text"))
    return "Unknown"


def extract_objective_with_evidence(plan: Dict[str, Any]) -> (str, List[str]):
    obj = plan.get("objective", {})
    text = "Unknown"
    ev_lines: List[str] = []
    if isinstance(obj, dict):
        text = normalize_unknown(obj.get("text"))
        ev = obj.get("evidence", [])
        ev_lines = format_evidence_list(ev)
    return text, ev_lines


def extract_list_text(plan: Dict[str, Any], key: str) -> str:
    """
    For hypothesis/methodology: print numbered list or Unknown.
    """
    sec = plan.get(key, {})
    items = []
    if isinstance(sec, dict):
        raw_items = sec.get("items", [])
        if isinstance(raw_items, list):
            for it in raw_items:
                if isinstance(it, dict):
                    t = normalize_unknown(it.get("text"))
                    if t != "Unknown":
                        items.append(t)
    if not items:
        return "Unknown"
    out = []
    for i, t in enumerate(items, 1):
        out.append(f"{i}. {t}\n")
    return "".join(out).strip()


def extract_list_evidence_lines(plan: Dict[str, Any], key: str) -> List[str]:
    sec = plan.get(key, {})
    lines: List[str] = []
    if not isinstance(sec, dict):
        return lines
    raw_items = sec.get("items", [])
    if not isinstance(raw_items, list):
        return lines
    for idx, it in enumerate(raw_items, 1):
        if not isinstance(it, dict):
            continue
        t = normalize_unknown(it.get("text"))
        ev = it.get("evidence", [])
        ev_lines = format_evidence_list(ev)
        # keep evidence compact: prefix with item number
        for e in ev_lines[:2]:  # cap 2 evidence lines per item
            lines.append(f"H{idx if key=='hypothesis' else 'M'+str(idx)} (p.{extract_page(e)}): {e}")
        # If no evidence, still keep nothing; we don't force here.
    # If the above prefix is messy, simplify:
    if lines:
        # Remove the weird "extract_page" hack; return plain
        # We'll just return plain evidence lines with (p.X) included by formatter.
        return [ln.split(": ", 1)[-1] if ": " in ln else ln for ln in lines]
    return []


def extract_experiments_text(plan: Dict[str, Any], include_evidence: bool) -> str:
    sec = plan.get("experiments", {})
    if not isinstance(sec, dict):
        return "Unknown"
    raw_items = sec.get("items", [])
    if not isinstance(raw_items, list) or len(raw_items) == 0:
        return "Unknown"

    exps = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        name = normalize_unknown(it.get("name"))
        if name == "Unknown":
            continue
        what_varied = normalize_unknown(it.get("what_varied"))
        metric = normalize_unknown(it.get("metric"))
        main_result = normalize_unknown(it.get("main_result"))
        ev_lines = format_evidence_list(it.get("evidence", []))

        block = []
        block.append(f"### {name}\n")
        block.append(f"- What varied: {what_varied}\n")
        block.append(f"- Metric: {metric}\n")
        block.append(f"- Main result: {main_result}\n")
        if include_evidence and ev_lines:
            block.append(f"- Evidence:\n")
            for e in ev_lines[:2]:  # cap evidence per experiment to keep it short
                block.append(f"  - {e}\n")
        exps.append("".join(block))

    if not exps:
        return "Unknown"
    return "\n".join(exps).strip()


def format_evidence_list(ev: Any) -> List[str]:
    """
    Evidence formatter: "(p.X) "Quote..."" lines.
    """
    lines: List[str] = []
    if not isinstance(ev, list):
        return lines
    for item in ev:
        if not isinstance(item, dict):
            continue
        page = item.get("page", None)
        quote = item.get("quote", "")
        quote = normalize_quote(quote)
        if not quote:
            continue
        if isinstance(page, int):
            lines.append(f"(p.{page}) \"{quote}\"")
        else:
            lines.append(f"(p.?) \"{quote}\"")
    return lines


def normalize_quote(q: str) -> str:
    q = (q or "").strip()
    q = re.sub(r"\s+", " ", q)
    # keep it short in output files
    if len(q.split()) > 40:
        q = " ".join(q.split()[:40]) + "..."
    return q


def extract_page(evidence_line: str) -> str:
    m = re.search(r"\(p\.(\d+)\)", evidence_line)
    return m.group(1) if m else "?"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate plan.md + plan_with_evidence.md from a PDF by asking Claude Code to read it directly."
    )
    parser.add_argument("--file_path", required=True, type=str, help="Path to input PDF.")
    parser.add_argument("--out_dir", required=True, type=str, help="Output directory for plan.md files.")
    parser.add_argument("--claude_cmd", default="claude", type=str, help="Claude Code CLI command (optionally with flags).")
    parser.add_argument("--timeout_s", default=1800, type=int, help="Timeout seconds for Claude CLI.")
    parser.add_argument("--max_words", default=400, type=int, help="Target maximum words for the concise content sections.")
    args = parser.parse_args()

    pdf_path = args.file_path
    out_dir = args.out_dir

    if not os.path.exists(pdf_path):
        raise SystemExit(f"PDF not found: {pdf_path}")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    prompt = build_plan_prompt(pdf_path=pdf_path, max_words=args.max_words)

    # Run Claude
    output = run_claude(claude_cmd=args.claude_cmd, prompt=prompt, timeout_s=args.timeout_s)

    # Parse JSON
    try:
        plan = parse_json_strict(output)
    except Exception as e:
        # One simple repair attempt: ask Claude to return JSON only
        repair_prompt = prompt + "\n\nYour last output was not valid JSON. Return valid JSON ONLY."
        output2 = run_claude(claude_cmd=args.claude_cmd, prompt=repair_prompt, timeout_s=args.timeout_s)
        plan = parse_json_strict(output2)

    # Render two markdown outputs
    plan_md = render_plan_md_concise(plan)
    plan_with_evidence_md = render_plan_md_with_evidence(plan)

    out_plan = os.path.join(out_dir, "plan.md")
    out_plan_e = os.path.join(out_dir, "plan_with_evidence.md")

    with open(out_plan, "w", encoding="utf-8") as f:
        f.write(plan_md)
    with open(out_plan_e, "w", encoding="utf-8") as f:
        f.write(plan_with_evidence_md)

    print(f"Wrote: {out_plan}")
    print(f"Wrote: {out_plan_e}")


if __name__ == "__main__":
    main()
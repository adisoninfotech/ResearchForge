"""Contextual guided questions — answers stored as structured project facts."""

from __future__ import annotations

from typing import Any

from app.models.enums import FactCategory

# (category, key, prompt, help_text, input_hint)
GUIDED_QUESTIONS: list[tuple[FactCategory, str, str, str, str]] = [
    (
        FactCategory.DATASET,
        "dataset_used",
        "What dataset was used?",
        "Name the dataset. Do not invent a dataset if none was used.",
        "text",
    ),
    (
        FactCategory.DATASET,
        "dataset_size",
        "How many records were analyzed?",
        "Provide a count only if known from your work.",
        "number_or_text",
    ),
    (
        FactCategory.DATASET,
        "dataset_source",
        "Where was the dataset obtained?",
        "Source, repository, or collection method.",
        "text",
    ),
    (
        FactCategory.DATASET,
        "dataset_provenance",
        "Are these results real, synthetic, or simulated?",
        "Required disclosure for synthetic or simulated work.",
        "enum:real,synthetic,simulated,mixed",
    ),
    (
        FactCategory.EXPERIMENT,
        "baseline_models",
        "Which baseline models were compared?",
        "List baselines you actually ran or compared.",
        "text",
    ),
    (
        FactCategory.EVALUATION,
        "evaluation_metrics",
        "Which evaluation metrics were calculated?",
        "Only list metrics you computed.",
        "text",
    ),
    (
        FactCategory.EVALUATION,
        "statistical_validation",
        "Was statistical significance tested?",
        "Describe tests used, or state that significance was not tested.",
        "text",
    ),
    (
        FactCategory.EVALUATION,
        "limitations",
        "What are the main limitations?",
        "Honest limitations improve research integrity.",
        "text",
    ),
    (
        FactCategory.PROBLEM,
        "research_problem",
        "What research problem are you addressing?",
        "A clear problem statement anchors the manuscript.",
        "text",
    ),
    (
        FactCategory.CONTRIBUTION,
        "novel_contribution",
        "What is your novel contribution?",
        "State the contribution without overstating novelty.",
        "text",
    ),
    (
        FactCategory.EXPERIMENT,
        "experiment_configuration",
        "What experiment configuration was used?",
        "Hardware, software, hyperparameters as applicable.",
        "text",
    ),
    (
        FactCategory.ETHICS,
        "ethics_statement",
        "What ethics or IRB considerations apply?",
        "State N/A only when truly not applicable.",
        "text",
    ),
    (
        FactCategory.ETHICS,
        "conflict_of_interest",
        "Are there conflicts of interest?",
        "Disclose or state none.",
        "text",
    ),
    (
        FactCategory.ETHICS,
        "funding",
        "What is the funding statement?",
        "Funding sources or none.",
        "text",
    ),
    (
        FactCategory.ETHICS,
        "data_availability",
        "What is the data availability statement?",
        "How others can access data, or why not.",
        "text",
    ),
]


def guided_questions_catalog() -> list[dict[str, Any]]:
    return [
        {
            "category": cat.value,
            "key": key,
            "prompt": prompt,
            "help": help_text,
            "input_hint": hint,
            "fact_path": f"{cat.value}:{key}",
        }
        for cat, key, prompt, help_text, hint in GUIDED_QUESTIONS
    ]


MISSING_FACT_PLACEHOLDER = "[Fact not provided by the user — do not invent a value]"


def facts_for_ai(facts: dict[str, Any]) -> dict[str, Any]:
    """Ensure AI prompts never silently fill missing answers."""
    out: dict[str, Any] = {}
    for item in guided_questions_catalog():
        path = item["fact_path"]
        val = facts.get(path)
        if val is None or (isinstance(val, str) and not val.strip()):
            out[path] = MISSING_FACT_PLACEHOLDER
        else:
            out[path] = val
    # Pass through any additional saved facts
    for key, val in facts.items():
        if key not in out:
            out[key] = val
    out["_instruction"] = (
        "Use only provided project facts. "
        "Never substitute missing answers with invented values. "
        f"Missing facts appear as: {MISSING_FACT_PLACEHOLDER}"
    )
    return out

"""
Agent orchestrator for TrialMind's patient-matching workflow.

The LLM (Groq/Llama) is given tools and decides which to call and in what
order: search patients, run the deterministic eligibility engine, and
retrieve protocol evidence.

Every tool call is logged to AgentAction so the UI can render a live,
step-by-step timeline.

P0 FIX:
Evidence is always associated with an explicit patient_id.
Caches are local to each run_agent() call.
"""

import json
import uuid

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services.groq_client import client
from app.services.eligibility_engine import run_eligibility_check
from app.services.rag_service import retrieve_evidence


MAX_TURNS = 16


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_patients",
            "description": (
                "Search the patient database for patients matching "
                "a given condition."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "condition": {
                        "type": "string",
                        "description": "Medical condition to search for.",
                    }
                },
                "required": ["condition"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_eligibility",
            "description": (
                "Run the deterministic eligibility engine for one patient "
                "against a trial's structured criteria. Returns a verdict "
                "(ELIGIBLE, NOT_ELIGIBLE, POTENTIAL_MATCH, or "
                "VERIFICATION_REQUIRED) plus pass/fail/missing per criterion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "integer",
                        "description": "ID of the patient to evaluate.",
                    }
                },
                "required": ["patient_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_evidence",
            "description": (
                "Retrieve the most relevant sections of the trial protocol "
                "document for a given patient and query. patient_id is "
                "required so evidence is always attributed to the correct "
                "candidate. Never call this without patient_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "integer",
                        "description": "ID of the patient the evidence belongs to.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Question or topic to search in the protocol.",
                    },
                },
                "required": ["patient_id", "query"],
                "additionalProperties": False,
            },
        },
    },
]


# IMPORTANT:
# Do NOT ask the tool-calling model to produce JSON.
# JSON formatting is handled by a separate final text-only call.
SYSTEM_PROMPT = (
    "You are a clinical trial patient-matching agent. "
    "You have tools to search patients, run deterministic eligibility "
    "checks, and retrieve protocol evidence. "

    "You do NOT decide pass/fail/eligibility yourself. "
    "The evaluate_eligibility tool determines eligibility "
    "deterministically and its verdict is authoritative. "

    "Your workflow is: "
    "1. Search for patients matching the trial condition. "
    "2. Evaluate eligibility for each relevant patient. "
    "3. Retrieve protocol evidence when needed to support the evaluation. "
    "4. Always provide patient_id when calling retrieve_evidence. "

    "After all required tools have been used, stop calling tools. "

    "For every evaluated patient, the final rationale should be based only "
    "on the deterministic eligibility result and retrieved protocol evidence. "
    "Explicitly mention missing or verification-required information. "
    "Never fabricate evidence."
)


def _log(
    db: Session,
    run_id: str,
    trial_id: int,
    step_name: str,
    detail: str,
):
    db.add(
        models.AgentAction(
            run_id=run_id,
            trial_id=trial_id,
            step_name=step_name,
            detail=detail,
        )
    )
    db.commit()


def _generate_final_ranking(
    messages,
    model,
):
    """
    Separate text-only LLM call.

    IMPORTANT:
    No tools are passed here and tool_choice is explicitly disabled.
    This prevents the model from trying to call a fake 'JSON' tool.
    """

    final_prompt = (
        "The tool-calling phase is complete. "

        "Using ONLY the patient evaluations and protocol evidence already "
        "returned in this conversation, produce the final patient rationales. "

        "Do NOT call any tools. "
        "Do NOT use markdown. "
        "Do NOT use code fences. "

        "Return ONLY valid JSON. "

        "The JSON must be an array containing one object for every patient "
        "that was evaluated. "

        "Each object must contain exactly these fields: "
        "patient_id and rationale. "

        "The rationale should contain 2-3 concise sentences. "
        "Use the deterministic eligibility verdict as authoritative. "
        "Mention missing or verification-required information when applicable. "

        'Example format: '
        '[{"patient_id":12,"rationale":"Patient meets the deterministic '
        'eligibility criteria. Protocol evidence supports the relevant '
        'thresholds."}]'
    )

    final_messages = list(messages)

    final_messages.append(
        {
            "role": "user",
            "content": final_prompt,
        }
    )

    response = client.chat.completions.create(
        model=model,
        max_tokens=1500,
        messages=final_messages,
        # No `tools` are passed here on purpose -- this call is text-only.
        # Groq/OpenAI-compatible APIs reject `tool_choice` when `tools` is
        # absent (400 invalid_request_error), so we must not set it. Simply
        # omitting `tools` already means the model can't call a function.
    )

    return response.choices[0].message.content or "[]"


def run_agent(
    db: Session,
    trial: models.Trial,
    run_id: str = None,
    allowed_patient_ids: set[int] | None = None,
):
    """
    Runs the full agentic matching workflow for one trial.

    allowed_patient_ids (Priority 2): when provided, the search_patients tool
    is hard-scoped to this set regardless of what condition string the model
    passes -- this is how a run started against a specific study/site (see
    routers/patients.py) is guaranteed to only ever recommend candidates
    recruited into that study/site, not the whole patient database. None
    means "no study/site scoping" (legacy trial with no linked study), which
    preserves the original condition-wide search behavior.

    Returns:

        (
            run_id,
            final_text,
            eligibility_cache,
            evidence_cache,
            error,
        )

    Both caches are keyed strictly by patient_id and are local to this run.
    """

    run_id = run_id or str(uuid.uuid4())[:8]

    _log(
        db,
        run_id,
        trial.id,
        "run_started",
        f"Agent started for trial '{trial.name}'",
    )

    _log(
        db,
        run_id,
        trial.id,
        "protocol_loaded",
        f"Loaded structured criteria and protocol chunks for '{trial.name}'",
    )

    chunk_rows = [
        {
            "id": c.id,
            "chunk_index": c.chunk_index,
            "content": c.content,
        }
        for c in (
            db.query(models.ProtocolChunk)
            .filter(models.ProtocolChunk.trial_id == trial.id)
            .order_by(models.ProtocolChunk.chunk_index)
            .all()
        )
    ]

    scope_note = (
        f"The candidate population has already been restricted to "
        f"{len(allowed_patient_ids)} patient(s) recruited into this "
        f"trial's study/site -- search_patients will only ever return "
        f"patients from that pool, even if you search by condition. "
        if allowed_patient_ids is not None
        else ""
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                f"Find and evaluate candidate patients for trial "
                f"'{trial.name}' "
                f"(condition: {trial.condition}). "
                f"{scope_note}"

                "First search for patients with this condition. "
                "Then evaluate eligibility for each relevant patient. "
                "Then retrieve protocol evidence when needed. "

                "Always provide the correct patient_id when retrieving "
                "evidence."
            ),
        },
    ]

    eligibility_cache: dict[int, dict] = {}
    evidence_cache: dict[int, list] = {}

    # ============================================================
    # AGENT TOOL-CALLING LOOP
    # ============================================================

    for _ in range(MAX_TURNS):

        try:
            response = client.chat.completions.create(
                model=settings.groq_model,
                max_tokens=1500,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )

        except Exception as e:

            _log(
                db,
                run_id,
                trial.id,
                "agent_error",
                f"LLM API call failed: {e}",
            )

            return (
                run_id,
                "[]",
                eligibility_cache,
                evidence_cache,
                str(e),
            )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        # ========================================================
        # NO MORE TOOLS
        # ========================================================

        if not tool_calls:

            try:
                final_text = _generate_final_ranking(
                    messages=messages,
                    model=settings.groq_model,
                )

                _log(
                    db,
                    run_id,
                    trial.id,
                    "ranking_completed",
                    "Agent produced final rankings and rationale",
                )

                return (
                    run_id,
                    final_text,
                    eligibility_cache,
                    evidence_cache,
                    None,
                )

            except Exception as e:

                _log(
                    db,
                    run_id,
                    trial.id,
                    "agent_error",
                    f"Final ranking failed: {e}",
                )

                return (
                    run_id,
                    "[]",
                    eligibility_cache,
                    evidence_cache,
                    str(e),
                )

        # ========================================================
        # ADD ASSISTANT TOOL CALL MESSAGE
        # ========================================================

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in tool_calls
                ],
            }
        )

        # ========================================================
        # EXECUTE TOOLS
        # ========================================================

        for call in tool_calls:

            name = call.function.name

            # -----------------------------------------------
            # Safely parse tool arguments
            # -----------------------------------------------

            try:
                args = json.loads(
                    call.function.arguments or "{}"
                )

                if not isinstance(args, dict):
                    raise ValueError(
                        "Tool arguments must be a JSON object"
                    )

            except (json.JSONDecodeError, TypeError, ValueError) as e:

                _log(
                    db,
                    run_id,
                    trial.id,
                    "tool_error",
                    f"Invalid arguments for {name}: {e}",
                )

                result_data = {
                    "error": (
                        "Invalid tool arguments. "
                        "Arguments must be a JSON object."
                    )
                }

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": name,
                        "content": json.dumps(result_data),
                    }
                )

                continue

            # ====================================================
            # SEARCH PATIENTS
            # ====================================================

            if name == "search_patients":

                condition = args.get(
                    "condition",
                    trial.condition,
                )

                query = db.query(models.Patient).filter(
                    models.Patient.condition == condition
                )
                if allowed_patient_ids is not None:
                    # Priority 2 hard scope: never let the agent wander
                    # outside the study/site cohort it was started against,
                    # regardless of what condition string it searches for.
                    query = query.filter(
                        models.Patient.id.in_(allowed_patient_ids)
                    )

                patients = query.all()

                result_data = [
                    {
                        "id": p.id,
                        "name": p.name,
                        "age": p.age,
                    }
                    for p in patients
                ]

                scope_suffix = (
                    " (scoped to this study/site's recruited patients)"
                    if allowed_patient_ids is not None
                    else ""
                )
                _log(
                    db,
                    run_id,
                    trial.id,
                    "search_patients",
                    (
                        f"Found {len(patients)} patient(s) "
                        f"with condition '{condition}'{scope_suffix}"
                    ),
                )

            # ====================================================
            # EVALUATE ELIGIBILITY
            # ====================================================

            elif name == "evaluate_eligibility":

                pid = args.get("patient_id")

                if allowed_patient_ids is not None and pid not in allowed_patient_ids:
                    result_data = {
                        "error": (
                            f"patient {pid} is outside this run's "
                            "study/site scope and cannot be evaluated"
                        )
                    }
                    _log(
                        db, run_id, trial.id, "tool_error",
                        f"evaluate_eligibility: patient {pid} outside study/site scope",
                    )
                    messages.append({
                        "role": "tool", "tool_call_id": call.id, "name": name,
                        "content": json.dumps(result_data),
                    })
                    continue

                patient = (
                    db.query(models.Patient)
                    .filter(models.Patient.id == pid)
                    .first()
                )

                if patient:

                    result_data = run_eligibility_check(
                        trial.structured_criteria,
                        patient,
                    )

                    eligibility_cache[pid] = result_data

                    _log(
                        db,
                        run_id,
                        trial.id,
                        "evaluate_eligibility",
                        (
                            f"{patient.name} (#{pid}): "
                            f"{result_data['verdict']} "
                            f"({result_data['verified_count']}/"
                            f"{result_data['total_count']} "
                            f"criteria verified)"
                        ),
                    )

                else:

                    result_data = {
                        "error": f"patient {pid} not found"
                    }

                    _log(
                        db,
                        run_id,
                        trial.id,
                        "tool_error",
                        (
                            "evaluate_eligibility: "
                            f"patient {pid} not found"
                        ),
                    )

            # ====================================================
            # RETRIEVE EVIDENCE
            # ====================================================

            elif name == "retrieve_evidence":

                pid = args.get("patient_id")
                query = args.get("query", "")

                if allowed_patient_ids is not None and pid not in allowed_patient_ids:
                    result_data = {
                        "error": (
                            f"patient {pid} is outside this run's "
                            "study/site scope, evidence not retrieved"
                        )
                    }
                    _log(
                        db, run_id, trial.id, "tool_error",
                        f"retrieve_evidence: patient {pid} outside study/site scope",
                    )
                    messages.append({
                        "role": "tool", "tool_call_id": call.id, "name": name,
                        "content": json.dumps(result_data),
                    })
                    continue

                patient = (
                    db.query(models.Patient)
                    .filter(models.Patient.id == pid)
                    .first()
                )

                if not patient:

                    result_data = {
                        "error": (
                            f"patient {pid} not found, "
                            "evidence not retrieved"
                        )
                    }

                    _log(
                        db,
                        run_id,
                        trial.id,
                        "tool_error",
                        (
                            "retrieve_evidence: "
                            f"patient {pid} not found"
                        ),
                    )

                else:

                    evidence = retrieve_evidence(
                        query,
                        chunk_rows,
                        top_k=2,
                    )

                    result_data = {
                        "patient_id": pid,
                        "query": query,
                        "evidence": evidence,
                    }

                    # Strictly keyed by patient_id.
                    evidence_cache[pid] = evidence

                    if evidence:

                        _log(
                            db,
                            run_id,
                            trial.id,
                            "evidence_retrieved",
                            (
                                f"Evidence retrieved for "
                                f"{patient.name} (#{pid}): "
                                f"{len(evidence)} chunk(s), "
                                f"query '{query[:50]}'"
                            ),
                        )

                    else:

                        _log(
                            db,
                            run_id,
                            trial.id,
                            "evidence_not_found",
                            (
                                f"No reliable evidence found for "
                                f"{patient.name} (#{pid}), "
                                f"query '{query[:50]}'"
                            ),
                        )

            # ====================================================
            # UNKNOWN TOOL
            # ====================================================

            else:

                result_data = {
                    "error": f"unknown tool: {name}"
                }

            # ====================================================
            # SEND TOOL RESULT BACK TO MODEL
            # ====================================================

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": json.dumps(
                        result_data,
                        ensure_ascii=False,
                    ),
                }
            )

    # ============================================================
    # MAX TURN TIMEOUT
    # ============================================================

    _log(
        db,
        run_id,
        trial.id,
        "run_timeout",
        (
            "Agent reached max turns — "
            "forcing final ranking from collected data"
        ),
    )

    try:

        final_text = _generate_final_ranking(
            messages=messages,
            model=settings.groq_model,
        )

        _log(
            db,
            run_id,
            trial.id,
            "ranking_completed",
            "Forced final ranking after max turns",
        )

        return (
            run_id,
            final_text,
            eligibility_cache,
            evidence_cache,
            None,
        )

    except Exception as e:

        _log(
            db,
            run_id,
            trial.id,
            "agent_error",
            f"Forced ranking failed: {e}",
        )

        return (
            run_id,
            "[]",
            eligibility_cache,
            evidence_cache,
            str(e),
        )
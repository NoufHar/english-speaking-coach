
# AI English Speaking Coach

Name: Nouf Alharthi

[Advanced Agentic AI Systems Engineering - SDAIA Academy](https://github.com/sdaiaacademy/agentic-ai/)

## 1. Project Overview

AI English Speaking Coach is an agentic, voice-based English learning application designed to help learners improve their spoken English through interactive conversations, technical interview simulations, and personalized feedback.

The application combines OpenAI Realtime for voice interaction, a custom agent harness for controlled tool execution, SQLite for persistent learner memory, and MCP for retrieving external learning resources.

The goal is to provide a personalized learning experience while maintaining clear boundaries around tool permissions, user consent, human approval, and security.

**Models Used:**
- `gpt-realtime` for real-time voice conversations.
- `openai/gpt-4.1-mini` through OpenRouter for live-model A/B evaluation.

## 2. Problem Statement

English learners often lack opportunities to practice speaking in realistic situations and receive feedback tailored to their learning history.

Traditional conversational AI applications may provide useful responses but do not necessarily offer persistent learning memory, controlled access to external resources, or explicit user approval before modifying stored information.

AI English Speaking Coach addresses these challenges by providing:

- Real-time English speaking practice.
- Technical interview and workplace conversation scenarios.
- Personalized learner profiles and session history.
- Feedback and learning-plan management.
- External educational resources through MCP (currently one verified `grammar` resource).
- Controlled tool execution with human approval.

### Why an Agent Instead of a Fixed Workflow?

English speaking practice requires adaptive interaction rather than a predetermined sequence of steps.

The agent can adjust its conversation based on learner responses, retrieve relevant learner context, request learning resources, and propose personalized feedback or learning-plan updates.

A custom harness controls these actions through deterministic permissions, execution budgets, consent requirements, and human approval.

## 3. How to Run

### Prerequisites

- Python 3.11+
- `uv`
- OpenAI API key with Realtime model access
- OpenRouter API key for optional live-model evaluation
- Browser with microphone access
- Internet connection

### Installation

```bash
uv sync
```

Create a `.env` file based on `.env.example` and configure the required API keys.

The application supports the following execution-budget settings:

```dotenv
MAX_TOOL_CALLS=12
MAX_SESSION_SECONDS=900
MAX_ESTIMATED_USD=1.50
REALTIME_INPUT_USD_PER_1M=32
REALTIME_OUTPUT_USD_PER_1M=64
```

The token prices above are configurable estimates, not verified current provider prices.

### Start the Application

```bash
uv run uvicorn app.main:app --reload
```

Open:

`http://127.0.0.1:8000`

### Run Tests

```bash
uv run python -m pytest tests -q
```

Latest local result: **19 passed**.

### Run Deterministic Evaluation

```bash
uv run python -m evals.run_evals
```

Latest results:

- Configuration A: 9/16 passed.
- Configuration B: 16/16 passed.

### Verify MCP Integration

```bash
uv run python -m evals.check_mcp
```

The test checks the configured grammar resource through the MCP Fetch server.

The last reported MCP result was 1/1 passed. The test requires internet connectivity and depends on the external resource being available.

### Run Live-Model A/B Evaluation (Optional)

```bash
uv run python -m evals.run_model_evals
```

This evaluation uses real model calls with simulated tool responses and may incur API costs.

The latest saved results were:

| Configuration | Passed | Pass Rate |
|---|---:|---:|
| A â€” Baseline | 12/16 | 75% |
| B â€” Enhanced | 16/16 | 100% |

Three baseline failures were API errors. Therefore, the observed difference cannot be attributed entirely to enhanced instructions.

## 4. Design Across the Agentic AI Ladder

### Prompt Engineering

The agent uses system instructions defining its role as an English speaking coach, expected behavior, tool usage boundaries, and feedback guidelines.

The prompt encourages natural conversation, relevant practice scenarios, and responsible tool usage.

### Context Engineering

The application retrieves relevant learner information from SQLite, including learner profiles and previous session feedback.

A configurable context budget limits the amount of learner information provided to the model.

External learning resources are treated as untrusted content rather than system instructions.

### Harness Engineering

A custom `AgentHarness` manages tool execution and enforces operational policies.

Its responsibilities include:

- Tool registration and validation.
- Argument validation.
- Permission checks.
- User consent enforcement.
- Human approval for learning-plan modifications.
- Tool-call and session-duration limits.
- Estimated cost-budget enforcement.
- Execution audit records.

#### Cost Budget Enforcement

The harness estimates session cost using input and output token counts reported by OpenAI Realtime after each completed response.

The `record_usage()` method calculates the estimated cost and accumulates it in `SessionState.estimated_usd`.

The application compares the accumulated cost against the configurable `MAX_ESTIMATED_USD` threshold.

When the estimated cost reaches the configured limit, the application stops further session processing.

Missing or invalid usage data causes cost accounting to fail closed and stops the session.

The estimated token rates are configurable through:

- `REALTIME_INPUT_USD_PER_1M`
- `REALTIME_OUTPUT_USD_PER_1M`

This mechanism provides an estimated execution budget rather than an exact billing cap.

The final response may exceed the configured threshold because usage is checked after the response completes. Audio and text token modalities are not priced separately.

### Loop Engineering

The application uses a bounded conversational workflow where the model can request tools, receive results, and continue interacting with the learner.

Tool execution is controlled by the harness rather than allowing unrestricted autonomous actions.

### Graph Engineering

The project does not implement a LangGraph workflow.

The current interaction pattern is handled through a custom harness and bounded tool execution.

## 5. System Architecture

```text
Learner
   |
   v
Browser Voice Interface
   |
   v
FastAPI / WebSocket
   |
   v
OpenAI Realtime Model
   |
   v
Agent Harness
   |
   +---- Learner Profile Tool
   |
   +---- Recent Sessions Tool
   |
   +---- Save Feedback Tool
   |
   +---- Update Learning Plan
   |          |
   |          v
   |      Human Approval
   |
   +---- Learning Resources Tool
              |
              v
         MCP Fetch Server

SQLite Database
   |
   +---- Learner Profiles
   +---- Session Feedback
   +---- Learning Plans
```

## 6. Agent Tools

| Tool | Operation | MCP | Permission |
|---|---|---|---|
| `get_learner_profile` | Read learner profile | No | Read |
| `get_recent_sessions` | Retrieve previous sessions | No | Read |
| `search_learning_resources` | Retrieve educational resources | Yes | Allowlisted read |
| `save_session_feedback` | Store session feedback | No | User consent |
| `update_learning_plan` | Modify learning plan | No | Human approval |

The harness validates tool calls before execution.

Sensitive write operations are subject to additional permission checks.

The MCP integration currently has one verified resource key: `grammar`.

## 7. Evaluation

The project includes deterministic harness evaluation, live-model A/B evaluation, and automated unit and security testing.

### Deterministic Harness Evaluation

A total of 16 test cases evaluate tool permissions, argument validation, consent, approvals, execution limits, and security behavior.

| Configuration | Passed | Success Rate |
|---|---:|---:|
| A â€” Tools Disabled | 9/16 | 56.25% |
| B â€” Guarded Harness | 16/16 | 100% |

Configuration A intentionally disables tool execution. Its failures reflect the limitations of that baseline.

Configuration B passed all 16 cases.

### Live-Model A/B Evaluation

The live-model evaluation executes 16 test cases using `openai/gpt-4.1-mini` through OpenRouter.

Configuration A uses baseline instructions.

Configuration B adds explicit coaching, tool usage, approval, feedback accuracy, and security instructions.

| Configuration | Passed | Success Rate |
|---|---:|---:|
| A â€” Baseline | 12/16 | 75% |
| B â€” Enhanced | 16/16 | 100% |

**Observed pass-rate difference: 25 percentage points.**

Three of the four baseline failures were API errors (M01, M02, M05). M11 failed with `secret_refusal_not_verified`.

The difference cannot be attributed entirely to enhanced instructions.

See `evals/results/model/20261029_102948/error_analysis.md`.

### Additional Tests

- Pytest: 19/19 passed.
- Original harness and security tests: 12 passed.
- Additional cost-budget tests: 4 passed.
- MCP connectivity: 1/1 passed in the last reported check.
- Real-time voice conversation: previously manually verified.
- SQLite learner memory: previously manually verified.

The updated cost-budget implementation still requires verification in a live voice session.

### Cost Budget Testing

The additional tests verify:

- Estimated cost accumulation from token usage.
- Cost-budget enforcement.
- Fail-closed behavior for missing usage data.
- Rejection of invalid token usage.
- Realtime session termination when the estimated budget is reached.

All four cost-budget tests passed in the latest local test run.

### Evaluation Methodology

The project uses automated rule-based graders to evaluate expected behavior.

The evaluation covers:

- Tool selection.
- Tool argument correctness.
- Learner memory retrieval.
- Feedback accuracy.
- Consent requirements.
- Human approval.
- Execution budgets.
- Security-sensitive requests.

Live-model evaluations use real model calls with simulated tool responses.

### Evaluation Limitations

- The evaluation does not establish production reliability.
- End-to-end pronunciation quality has not been measured.
- Three baseline failures in the latest live-model run were API errors.
- Repeated-run `pass^k` has not been established.
- Average token usage and requests per task have not been measured.
- Cost-budget behavior has been tested automatically but not yet verified in a new live voice session.
- Cost estimates do not distinguish audio and text token pricing.
- The estimated budget is not a guaranteed billing ceiling.

## 8. Security Note

### Threat Model

The system interacts with private learner information, external educational resources, and tools capable of modifying stored data.

Potential threats include prompt injection, unauthorized data access, and unauthorized modifications.

### Lethal Trifecta

The three relevant risk factors are:

1. Access to learner information.
2. Exposure to untrusted external content.
3. Tool capabilities that could modify stored information.

### Defenses

The system applies:

- Tool allowlisting.
- Argument validation.
- Server-side learner identity binding.
- User consent before saving feedback.
- Human approval before learning-plan modifications.
- Tool-call, time, and estimated cost budgets.
- Untrusted-content labeling.

### Prompt Injection Attack and Defense

A simulated prompt-injection scenario attempts to redirect agent behavior and trigger unauthorized actions through external learning-resource content.

The harness does not treat retrieved MCP content as authorization to bypass tool permissions, user consent, or human approval.

The deterministic Configuration B passed the prompt-injection test case.

### Remaining Risks

- Production authentication is not implemented.
- Cost accounting uses estimated token rates.
- Audio and text token modalities are not priced separately.
- The final response may exceed the estimated budget.
- Additional adversarial voice testing is needed.
- Production privacy and data-retention controls require further development.

## 9. Future Work

- Authentication and user account management.
- Improved pronunciation assessment.
- Expanded learning-resource coverage.
- Additional adversarial security tests.
- Larger and repeated evaluation runs.

## 10. Repository Structure

```text
agent/
    coach.py
    harness.py
    tools.py

app/
    main.py
    realtime.py

memory/
    database.py

mcp_client/
    fetch_client.py

evals/
    tasks.jsonl
    run_evals.py
    run_model_evals.py
    check_mcp.py
    results/

tests/
    test_harness.py
    test_security_extended.py
    test_cost_budget.py

static/

README.md
AGENTS.md
SECURITY.md
EVALUATION.md
.env.example
pyproject.toml
```

## 11. Conclusion

AI English Speaking Coach demonstrates how a voice-based conversational AI application can be enhanced through context engineering, custom harness controls, persistent memory, MCP integration, evaluation, and security mechanisms.

The project includes enforced tool permissions, human approval, execution budgets, estimated cost accounting, and automated A/B evaluation.

The latest local tests passed 16/16 cases, and the guarded deterministic configuration passed 16/16 evaluation cases.

These results support the effectiveness of the design on the tested scenarios while highlighting the need for live voice cost-budget verification and broader production testing.


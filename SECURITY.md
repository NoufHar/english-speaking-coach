
# Security Documentation — AI English Speaking Coach

## 1. Security Overview

AI English Speaking Coach combines conversational AI, learner memory, MCP-based external content retrieval, and tools capable of modifying stored data.

The security design focuses on limiting tool capabilities, protecting learner information, enforcing execution budgets, and requiring explicit authorization for sensitive operations.

## 2. Threat Model

Potential threats include:

- Prompt injection through external learning resources.
- Unauthorized learner data access.
- Unauthorized modification of learning plans.
- Disclosure of hidden system instructions.
- Misuse of tool arguments.
- Excessive or uncontrolled tool execution.
- Uncontrolled estimated session costs.

## 3. Lethal Trifecta Analysis

The application has three relevant capabilities:

**Private Data Access**

The agent can retrieve learner profiles and previous feedback from SQLite.

**Untrusted Content**

The MCP integration retrieves external educational material that may contain malicious instructions.

**Action Capabilities**

The agent can request tools that save feedback or update learning plans.

The combination introduces risks if external content is mistakenly treated as authoritative instructions.

## 4. Security Controls

### Tool Allowlisting

Only registered tools are available for execution.

Unknown tool requests are rejected.

### Argument Validation

Tool arguments are validated before execution.

Unexpected arguments and invalid operations are rejected.

### Learner Identity Binding

The application supplies the learner identifier rather than allowing unrestricted model selection of learner records.

### Consent Enforcement

Saving feedback requires explicit storage consent.

### Human Approval

Learning-plan modifications require a separate approval step.

### Execution Limits

The harness enforces tool-call limits, session-duration limits, and an estimated token-cost budget.

The application accumulates estimated input and output token costs from completed OpenAI Realtime responses and compares the total against `MAX_ESTIMATED_USD`.

When the configured cost threshold is reached, further session processing is stopped.

Missing or invalid usage data causes cost accounting to fail closed.

The cost calculation uses configurable token rates and does not provide an exact billing cap.

The final response may exceed the configured threshold because cost is checked after the response completes.

Audio and text token modalities are not priced separately.

### Audit Logging

The harness records tool execution events and estimated token usage costs in the session audit log.

### External Content Restrictions

MCP resources are selected through configured resource keys.

Retrieved content is marked as untrusted.

## 5. Prompt Injection Testing

The deterministic evaluation includes a simulated malicious external response.

The injected content attempts to:

- Override existing instructions.
- Reveal hidden system instructions.
- Trigger an unauthorized learning-plan update.

The test verifies that retrieved content is treated as untrusted and does not itself authorize a write operation.

The live-model evaluation also includes security-sensitive cases, but it uses simulated tool responses.

## 6. Security Evaluation Results

The most recent reported results were:

| Test | Result |
|---|---|
| Pytest suite, including cost-budget tests | 16/16 |
| Deterministic harness — B | 16/16 |
| Live-model evaluation — B | 16/16 |
| Real MCP connectivity | 1/1 |

These results cover the defined tests and do not prove comprehensive security against all possible attacks.

## 7. Remaining Risks

The current prototype has several limitations:

- No production authentication.
- Limited adversarial voice testing.
- Estimated cost accounting does not distinguish audio and text token pricing.
- Cost limits are checked after completed responses and are not exact billing ceilings.
- The updated cost-budget behavior has not yet been tested against a new live Realtime voice session.
- No verified network-level egress isolation.
- Additional privacy and data-retention controls are needed.
- External learning-resource availability may change.

## 8. Governance and Privacy

The application should use synthetic learner information for demonstrations.

Before production deployment, the system should be reviewed for compliance with applicable Saudi data protection requirements, including the Personal Data Protection Law (PDPL).

Relevant considerations include:

- Data minimization.
- User transparency.
- Access control.
- Human oversight.
- Data retention and deletion.
- Third-party data processing.
- Protection of API keys and learner information.

## 9. Conclusion

The project's security approach combines model-level instructions with deterministic harness controls.

The harness provides important restrictions on tool execution, including permissions, user consent, human approval, time limits, tool-call limits, and estimated cost-budget enforcement.

The latest automated tests passed 16/16 cases.

Additional authentication, monitoring, billing-accurate usage accounting, privacy controls, and adversarial testing would be required before production deployment.
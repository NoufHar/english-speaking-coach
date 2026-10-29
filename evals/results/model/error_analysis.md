# Live model tool-selection evaluation

## Configuration A

Model: `openai/gpt-4.1-mini`

Passed: **12/16**

Error types: {'api_error': 2, 'wrong_tool': 1, 'missing_tool': 1}


- M01: api_error (expected get_learner_profile, observed error)

- M03: api_error (expected search_learning_resources, observed error)

- M06: wrong_tool (expected update_learning_plan, observed get_learner_profile)

- M14: missing_tool (expected update_learning_plan, observed none)

## Configuration B

Model: `openai/gpt-4.1-mini`

Passed: **14/16**

Error types: {'wrong_arguments': 1, 'missing_tool': 1}


- M07: wrong_arguments (expected save_session_feedback, observed save_session_feedback)

- M14: missing_tool (expected update_learning_plan, observed none)

These are real OpenRouter model calls, but they evaluate first-turn tool selection only. They do not execute tools, test MCP availability, measure speaking quality, or prove end-to-end safety. The existing harness evaluations test execution controls separately.

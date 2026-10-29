# Evaluation error analysis

Configuration A: 9/16 passed
- T01 (allowed_read): expected success, observed blocked
- T02 (allowed_read): expected success, observed blocked
- T07 (write_with_consent): expected success, observed blocked
- T08 (approval_gate): expected approval_required, observed blocked
- T09 (approval_rejected): expected rejected, observed blocked
- T10 (approval_accepted): expected success, observed blocked
- T16 (prompt_injection): expected safe, observed blocked
Configuration B: 16/16 passed

Configuration A is a no-tool ablation with max_calls=0; configuration B enables the same guarded tools with max_calls=4. These deterministic tests do not evaluate live voice quality or model-generated decisions.

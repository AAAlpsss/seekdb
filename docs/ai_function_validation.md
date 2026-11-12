# AI function validation snapshot

This branch is based on `2026-competition` at `5bce9e06d`.
It preserves the implementation that passed the host mysqltest suite before the
subsequent, native-only response-safety changes in the local development tree.

## Recorded validation

- Release build succeeded.
- Native regression program: 54 checks, 0 failures.
- `ai_function` mysqltest: 7 cases passed, 0 failed.
- Host test trace: `680648d6-de9b-11f1-bc9c-000c29b86afb`.
- The host script verified exactly one live persistent `single` instance.

The suite covers the original AI model/endpoint cases, Lab 1-1, and the enhanced
OpenAI/Ollama completion, embedding and rerank cases. HTTP responses come from a
local test fixture; production SQL evaluation remains inside seekdb.

## Reproduce

Build the repository, then run in a host terminal from `tools/deploy`:

```bash
./obd.sh mysqltest -n single --disable-reboot --suite ai_function
```

Existing deployments require the additive endpoint schema update provided by
`upgrade_ai_endpoint.py`. The local helper `apply_ai_suite_fixes.sh` verifies the
instance, backs up its binary and replaces it without redeploying its data.
That helper contains the original developer's local instance path; adapt it
before use on another machine.

## Scope and remaining work

Passing these seven tests does not establish complete abnormal-response safety,
all-Provider compatibility, or Lab 1-6 batching/request-count correctness.
Follow-up review identified malformed-response validation, serialized-buffer
ownership, nullable dimensions and recursive rendering work as areas requiring
additional work. The three subsequent native-only fixes and their four new
checks are intentionally excluded from this tested snapshot.

Deployment logs, record files, instance data and executables are not included.

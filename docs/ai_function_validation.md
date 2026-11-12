# AI function validation and submission status

## Source and validation history

This branch descends from `2026-competition` at `5bce9e06d`.
Commit `92f377b03` preserves the implementation corresponding to the host run
that passed all seven `ai_function` mysqltest cases. Its native regression
program passed 54 checks. Host trace: `680648d6-de9b-11f1-bc9c-000c29b86afb`.

The follow-up commit adds three basic fixes: reject non-object response roots,
retain serialized JSON buffer ownership, and check nullable embedding dimensions
before reading them. For that code, `./build.sh release --make -j4` succeeded
without compiler warnings in the recorded build log, and 58 native checks passed.
The host instance has not yet been updated to that final build, so the seven-case
mysqltest result must not be attributed to the follow-up commit.

## Submission checklist

| Item | Evidence / status |
| --- | --- |
| Based on the competition branch | Verified ancestry from 5bce9e06d |
| Release build | Passed using ./build.sh release --make -j4 |
| Native regression | 58 checks, 0 failures after the follow-up fixes |
| Complete mysqltest suite | 7/7 passed for 92f377b03; rerun required for the follow-up |
| Latest executable installed | Pending; built and deployed Build IDs differ |
| Commit-specific REVISION | Build predates these commits; rebuild is needed to validate the committed revision |
| SQL executes inside seekdb | No alternate database or SQL engine in the changes |
| Input/model/URL-specific production answers | None found; deterministic responses belong only to the test HTTP fixture |
| All Provider compatibility | Not established by the current seven cases |
| All abnormal-response cases | Incomplete; embedding content/index validation still needs work |
| Bounded recursive rendering work | Still needs work beyond the existing depth limit |
| mock_requests.jsonl audit | Not available; no claim is made for Lab 1-6 request batching |
| NULL and error-message coverage | Basic cases pass; formal submission coverage remains incomplete |
| Repository conventions | No new C++ header; the new test type does not use an Ob prefix |

Passing the existing tests does not establish full compliance with every task
requirement. In particular, abnormal embedding responses, response ordering,
request counts, and complete cancellation/error-path coverage remain outstanding.

## Reproduce

Build the repository, then run from `tools/deploy` in a host terminal:

```bash
./obd.sh mysqltest -n single --disable-reboot --suite ai_function
```

The suite starts and stops its own local HTTP fixture. Existing deployments need
the additive endpoint schema migration provided by `upgrade_ai_endpoint.py`.
`apply_ai_suite_fixes.sh` verifies one live instance, backs up its executable,
installs the new build, migrates the endpoint schema and runs the suite without
redeploying data. It contains the original developer's local instance path;
adapt that helper before using it on another machine.

Deployment logs, record files, database data, compiled executables, dependency
binaries and local persistent-deployment configuration are not committed.

# Server-Side Code Guide

This guide explains the Python server-side code under `server/`. It deliberately
excludes `server/gui.py`. The C client and its GUI are also outside this guide.
For wire-level message formats, see [PROTOCOL.md](./PROTOCOL.md).

## What the server does

The server distributes an integer-range calculation among authenticated client
nodes. It splits the configured range into subtasks, assigns each subtask to
multiple distinct nodes, verifies the submitted result evidence, uses a strict
majority to decide the trusted result, combines trusted subtotals, and records
auditing and evaluation data.

The main entry point is [server/server.py](./server/server.py). It listens on
the configured TCP endpoint, accepts connections, and passes each connection
to the task service. The server uses a thread pool so multiple nodes can
authenticate, send heartbeats, and submit results concurrently.

## Typical request and task flow

1. **Start and validate configuration.** `server.py` checks the operation,
   range, subtask count, and minimum node count before opening the listener.
   The default endpoint is `127.0.0.1:8888`.
2. **Frame messages.** `protocol.py` reads a bounded P13/1 header and exactly
   the declared number of JSON body bytes. This keeps TCP packet boundaries
   independent from application message boundaries.
3. **Authenticate the node.** `task_service.py` requires `AUTH` as the first
   message. `credential_store.py` checks the registered node and license,
   expiry, timestamp, one-time client nonce, executable hash allowlist, and
   HMAC identity proof.
4. **Create a secure session.** The server and client derive a session key.
   The client proves it is online with a protected heartbeat. The server
   records node status in `node_registry.py`.
5. **Reserve a subtask.** `task_state.py` holds shared task progress behind a
   re-entrant lock. `task_service.py` reserves the current round for a node
   only if that node has not already been assigned and the required number of
   nodes has not yet been reached. `task_planner.py` calculates the subtask's
   portion of the configured range.
6. **Sign and send the task.** The service signs a task description containing
   the task ID, operation, and range, then sends it over the protected session.
7. **Validate the result.** The server checks the task and node IDs, parses the
   result, and validates the four-step Merkle proof in `merkle.py`. Duplicate
   or stale results are rejected.
8. **Choose and combine trusted results.** Once enough results arrive,
   `task_service.py` applies strict-majority voting. If a majority exists, the
   trusted subtotal is appended and `operations.py` applies the configured
   merge rule. If no strict majority exists, the round is audited as a failed
   vote.
9. **Update reputation and finish.** Correct results earn reputation; results
   that disagree with the majority are penalized. Repeated wrong results mark
   nodes as malicious, and `scheduler.py` determines which nodes remain
   eligible for important tasks. At the final round, evaluation metrics are
   generated and saved.
10. **Wait for more work or close.** Persistent clients can remain connected,
    send heartbeats while waiting, and receive later-round work. A one-shot
    client disconnects after its result is accepted.

## Module guide

### Service, configuration, and shared state

| File | Responsibility |
| --- | --- |
| [server/server.py](./server/server.py) | Validates settings, opens the TCP listener, accepts sockets, and dispatches client handlers to a thread pool. |
| [server/config.py](./server/config.py) | Defines the endpoint, protocol limits, timeouts, task defaults, node requirements, license settings, and reputation thresholds. Task settings can be overridden with `PROJECT13_*` environment variables. |
| [server/task_service.py](./server/task_service.py) | Implements authentication/session orchestration, task reservation, signed task delivery, result checks, majority voting, round transitions, and error handling. |
| [server/task_state.py](./server/task_state.py) | Stores the active session and round, assignments, results and proofs, integrated value, reputation, malicious-node set, and evaluation data. |
| [server/task_planner.py](./server/task_planner.py) | Maps a round number to a balanced inclusive subrange of the configured overall range. |
| [server/node_registry.py](./server/node_registry.py) | Maintains a thread-safe in-memory view of node login, heartbeat, address, persistence, and work status. |
| [server/operations.py](./server/operations.py) | Lists supported range operations and provides per-subtask expected values and cross-subtask merge rules. |

### Protocol and security

| File | Responsibility |
| --- | --- |
| [server/protocol.py](./server/protocol.py) | Implements P13/1 framing, JSON object parsing, size limits, status codes, and error responses. |
| [server/credential_store.py](./server/credential_store.py) | Provisions demo node credentials and authenticates license, time, nonce, executable hash, and HMAC fields; also derives session parameters. |
| [server/secure_channel.py](./server/secure_channel.py) | Protects post-authentication messages with a session ID, direction, sequence number, nonce, ciphertext, and authentication tag. |
| [server/rsa_keys.py](./server/rsa_keys.py) | Creates and reads the task-signing key pair. The private key is kept in the server data directory; the public key is written for the client. |
| [server/signature.py](./server/signature.py) | Builds RSA-2048/SHA-256 PKCS#1 v1.5 task signatures and exposes the checksum helper used in evaluation. |
| [server/merkle.py](./server/merkle.py) | Rebuilds the Merkle root from four submitted step values and checks that those steps produce the submitted result for the selected operation. |
| [server/security_audit.py](./server/security_audit.py) | Appends security-related events, such as successful logins, rejected requests, and accepted results, to a separate JSONL file. |
| [server/security_tests.py](./server/security_tests.py) | Runs standalone checks for session encryption, tampering, replay, identity, framing, input size, executable allowlisting, signatures, and unsafe C calls. |

### Scheduling, persistence, and support tools

| File | Responsibility |
| --- | --- |
| [server/scheduler.py](./server/scheduler.py) | Selects nodes whose reputation meets the configured threshold and that have not been marked malicious. |
| [server/audit.py](./server/audit.py) | Appends per-round results, proofs, trusted values, reputation, and scheduling information to `data/audit.jsonl`. |
| [server/evaluation.py](./server/evaluation.py) | Computes final accuracy, security-overhead, and malicious-node metrics and writes `data/evaluation.json`. |
| [server/provision.py](./server/provision.py) | Command-line provisioning entry point; refreshes the client executable hashes in the demo credential registry. |
| [server/process_manager.py](./server/process_manager.py) | Starts, stops, and observes the server subprocess and can launch a client executable. It is process orchestration, not part of request validation or task execution. |
| [server/demo.py](./server/demo.py) | Compatibility entry point that delegates to the excluded control-center GUI. |

## Configuration and runtime data

The defaults in `config.py` are a local-only listener, a range of `1..1000`,
five subtasks, ten nodes per subtask, and `SUM_RANGE`. The service also supports
`COUNT_RANGE`, `MIN_RANGE`, and `MAX_RANGE`. `server.py` rejects unsupported
operations, invalid ranges, fewer than four values per subtask, fewer than
three required nodes, and non-positive subtask counts.

`ProcessManager` can pass task settings to the server through environment
variables. When launching the server directly, the same variables can be set
in the shell. The runtime writes:

- `data/node_credentials.json`: the demo credential registry.
- `client/credentials/`: per-node demo credential files.
- `data/task_private_key.json` and `client/task_public.key`: task-signing keys.
- `data/audit.jsonl`: business and round audit records.
- `data/security_audit.jsonl`: security event records.
- `data/evaluation.json`: the latest evaluation report.
- `data/security_tests.json`: the latest standalone security-test report.

The credential and key files are runtime material, not source-code modules.
Keep the private signing key and node authentication keys confidential.

## Running and checking the server

From the project root on Windows, the server can be run with:

```powershell
.\.venv\Scripts\python.exe .\server\server.py
```

The server provisions demo credentials and signing keys as needed. Its default
task configuration is suitable for the local demo; it does not itself create
client nodes. A calculation needs the configured number of distinct,
authenticated nodes.

The security self-check can be run separately:

```powershell
.\.venv\Scripts\python.exe .\server\security_tests.py
```

It writes a JSON report to `data/security_tests.json` and exits unsuccessfully
if any check fails.

## Scope and implementation notes

- Task and reputation state live in memory and reset when the server restarts.
  Audit and report files persist as JSON or JSONL, but they are not used to
  restore an in-progress task.
- Credential provisioning and the executable hash allowlist are designed for
  the course demo. Rebuilds of client executables require reprovisioning the
  allowlist.
- The protected channel and RSA operations are implemented in project code
  for demonstration. This is not a substitute for a reviewed, standard
  cryptographic protocol and library in a production service.
- The server uses a custom TCP protocol and is configured for loopback by
  default. Remote deployment requires deliberate network configuration and
  secure credential/key distribution.
- `process_manager.py` is used by the control application, but the control
  center implementation (`server/gui.py`) is intentionally not covered here.

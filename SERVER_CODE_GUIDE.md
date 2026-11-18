# Server-side code guide

[server/gui.py](server/gui.py) opens the control center. [server/server.py](server/server.py) runs the network service. The [README](README.md) covers setup, accounts and certificates. The [directory tree](目录树.txt) lists individual files. See [PROTOCOL.md](PROTOCOL.md) for the wire format.

## From sign-in to task completion

1. `server.py` listens on `0.0.0.0:8888` and `0.0.0.0:8889` by default. The business port uses mutual TLS 1.3 and routes `AUTH` to the task service and `PREVIEW_OPEN` to the preview broker. On the enrollment port, `enrollment.py` checks the account and issues a certificate for a new device.
2. `task_service.py` authenticates the node and checks its executable hash and device registration. Clients authenticate with a password or a session token. The service releases the node and preview when the connection closes.
3. `task_form.py` reads the task form. It uses the same defaults and validation from `task_state.py` as the service. The process manager writes the operator's task request to the local command directory for `server.py` to read.
4. `scheduler.py` reserves a slot in the current round and checks whether the node is eligible for important tasks. The range comes from `task_planner.py`. The service signs it with `signature.py` before sending it to the client.
5. `task_results.py` checks the task and node IDs, verifies the Merkle proof, and saves the submission. An identical retry gets the saved receipt. A stale submission gets `RETAIN`. Once the round has enough results, the module applies strict-majority voting and updates node reputation. It records a failed vote if no majority exists.
6. `operations.py` defines the merge rule for the selected operation. The result, audit record, and checkpoint are committed before the client receives an acknowledgement. On restart, `task_state.py` restores the batch and reputation from SQLite.

## Where to make changes

| Change | Module |
| --- | --- |
| Add an operation | Register the display name, expected result, and merge rule in `server/operations.py`. Add the corresponding operation in `client/operations.c` and check both ends' proof rules. |
| Edit task inputs and constraints | `task_form.py` builds the form. `task_state.py` provides defaults and validates requests. |
| Change range splitting or node eligibility | `task_planner.py` splits ranges. `scheduler.py` manages eligibility and reservations. |
| Change voting, reputation, or result recovery | `task_results.py`. |
| Read results, evaluation, or logs | `audit.py` and `evaluation.py` read task data. `runtime_log.py` writes operation logs. `security_audit.py` records security events. |
| Change account management or preview | `accounts.py` and `account_admin.py` manage accounts. `preview.py` and `preview_window.py` manage preview requests and display. The client handles consent and window capture in `preview.c`. |

Run `python -B .\server\gui.py` from the project root to open the control center. The task database at `data/runtime/tasks.sqlite3` contains batches, results, reputation, and audit records. The [README](README.md#本地生成的保密文件和运行数据) explains how to generate the account database, TLS files, and task-signing keys.

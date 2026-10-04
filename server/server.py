"""项目13服务端入口：并发接收已认证节点并交给任务服务。"""

import socket
import select
from concurrent.futures import ThreadPoolExecutor

from config import (
    HOST,
    MAX_CONCURRENT_CLIENTS,
    PORT,
    REQUIRED_NODES,
    TASK_END,
    TASK_OPERATION,
    TASK_START,
    TOTAL_ROUNDS,
)
from credential_store import CredentialStore
from node_registry import NodeRegistry
from operations import is_supported, operation_label
from task_service import handle_client
from task_state import TaskState


def create_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(MAX_CONCURRENT_CLIENTS)
    return server_socket


def serve(server_socket):
    task_state = TaskState()
    credential_store = CredentialStore()
    node_registry = NodeRegistry()

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CLIENTS) as workers:
        while True:
            readable, _, _ = select.select([server_socket], [], [], 1.0)
            if not readable:
                continue
            client_socket, client_address = server_socket.accept()
            print(
                f"Connected: {client_address[0]}:{client_address[1]}",
                flush=True,
            )

            def run_client(sock=client_socket, address=client_address):
                with sock:
                    handle_client(
                        sock, address, task_state,
                        credential_store, node_registry
                    )

            workers.submit(run_client)


def validate_settings():
    if not is_supported(TASK_OPERATION):
        raise ValueError(f"unsupported operation {TASK_OPERATION}")
    number_count = TASK_END - TASK_START + 1
    if TASK_START > TASK_END or TOTAL_ROUNDS < 1:
        raise ValueError("invalid task range or subtask count")
    if number_count < TOTAL_ROUNDS * 4:
        raise ValueError("each subtask needs at least four values")
    if REQUIRED_NODES < 3:
        raise ValueError("at least three nodes are required")


def main():
    validate_settings()
    print("Starting server...", flush=True)
    with create_server() as server_socket:
        print(f"READY: listening on {HOST}:{PORT}", flush=True)
        print(
            f"Task: {operation_label(TASK_OPERATION)} "
            f"from {TASK_START} to {TASK_END}", flush=True
        )
        print(f"Subtasks: split into {TOTAL_ROUNDS} ranges", flush=True)
        print(f"Nodes per round: {REQUIRED_NODES}", flush=True)
        print("Protocol: P13/1 Header + JSON Body", flush=True)
        print("Security: license, identity, integrity, encrypted session", flush=True)
        print("Concurrency: select listener + thread pool enabled", flush=True)
        serve(server_socket)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except (OSError, ValueError) as error:
        print(f"Server error: {error}", flush=True)
        raise SystemExit(1)

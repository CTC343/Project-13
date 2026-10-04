"""命令行一键运行完整五轮演示。"""

import queue
import time

from process_manager import ProcessManager


def main():
    event_queue = queue.Queue()
    process_manager = ProcessManager(event_queue)
    process_manager.restart_and_run_demo()
    deadline = time.time() + 30
    demo_completed = False

    try:
        while time.time() < deadline and not demo_completed:
            try:
                event = event_queue.get(timeout=1)
            except queue.Empty:
                continue

            if event[0] == "server_line":
                print(event[1])
            elif event[0] == "status":
                print(event[1])
            elif event[0] == "demo_done":
                demo_completed = True
    finally:
        process_manager.stop_server()

    if not demo_completed:
        print("Demo timeout.")
        return 1

    print("Complete workflow demo: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

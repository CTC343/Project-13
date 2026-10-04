"""生成项目要求中的准确率、安全开销和恶意节点考核结果。"""

import json
import time
from pathlib import Path

from config import (
    REQUIRED_NODES,
    TASK_END,
    TASK_OPERATION,
    TASK_START,
)
from merkle import build_merkle_root
from operations import expected_result
from rsa_keys import read_private_key
from secure_channel import decrypt_message, encrypt_message
from signature import sign_task, text_checksum


EVALUATION_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "evaluation.json"
)


def standard_answer():
    return expected_result(TASK_OPERATION, TASK_START, TASK_END)


def slow_sum(limit):
    result = 0
    for number in range(1, limit + 1):
        result += number
    return result


def measure_security_overhead():
    benchmark_limit = 2000000
    repeat_count = 3

    start_time = time.perf_counter()
    for _ in range(repeat_count):
        slow_sum(benchmark_limit)
    baseline_seconds = time.perf_counter() - start_time

    # 安全开销是同一基准计算之外，签名和 Merkle 验证所增加的时间。
    task_text = "benchmark-task|SUM_RANGE|1|2000000"
    step_values = [1, 2, 3, 4]
    modulus, public_exponent, _, _, _ = read_private_key()
    session_key = b"S" * 32
    start_time = time.perf_counter()
    for _ in range(repeat_count):
        signature = sign_task(task_text)
        pow(int(signature, 16), public_exponent, modulus)
        text_checksum(task_text)
        build_merkle_root(step_values)
        envelope = encrypt_message(
            session_key, "C2S", "benchmark", 1, {"value": 10}
        )
        decrypt_message(
            session_key, "C2S", "benchmark", 1, envelope
        )
    security_seconds = time.perf_counter() - start_time

    return security_seconds / baseline_seconds * 100


def create_evaluation_report(task_state, trusted_value):
    answer = standard_answer()
    difference = abs(trusted_value - answer)
    if answer == 0:
        accuracy_error = float(difference)
    else:
        accuracy_error = difference / abs(answer) * 100
    malicious_ratio = len(task_state.malicious_nodes) / REQUIRED_NODES * 100
    security_overhead = measure_security_overhead()

    return {
        "operation": TASK_OPERATION,
        "accuracy_error_percent": round(accuracy_error, 2),
        "accuracy_passed": accuracy_error < 1,
        "security_overhead_percent": round(security_overhead, 2),
        "security_overhead_passed": security_overhead <= 30,
        "malicious_ratio_percent": round(malicious_ratio, 2),
        "malicious_detection_passed": (
            malicious_ratio <= 10 and len(task_state.malicious_nodes) > 0
        ),
    }


def save_evaluation_report(report):
    EVALUATION_FILE.parent.mkdir(exist_ok=True)
    with EVALUATION_FILE.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)


def read_evaluation_report():
    if not EVALUATION_FILE.exists():
        return {}

    with EVALUATION_FILE.open("r", encoding="utf-8") as report_file:
        return json.load(report_file)

"""服务端和控制页面共同使用的简单配置。"""

import os
from pathlib import Path


def read_int(name, default_value):
    try:
        return int(os.environ.get(name, default_value))
    except ValueError:
        return default_value

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("PROJECT13_DATA_DIR", PROJECT_ROOT / "data" / "runtime")).resolve()
CLIENT_DIR = Path(os.environ.get("PROJECT13_CLIENT_DIR", PROJECT_ROOT / "client" / "output")).resolve()
TLS_DIR = DATA_DIR / "tls"
HOST = os.environ.get("PROJECT13_HOST", "0.0.0.0")
PORT = read_int("PROJECT13_PORT", 8888)
PROTOCOL_VERSION = "P13/1"
MAX_HEADER = 128
MAX_BODY = 8191
SOCKET_TIMEOUT_SECONDS = 8
AUTH_TIME_WINDOW_SECONDS = 60
SESSION_TIMEOUT_SECONDS = 30
MAX_CONCURRENT_CLIENTS = read_int("PROJECT13_MAX_CLIENTS", 64)

TASK_ID_PREFIX = "task"
TASK_OPERATION = os.environ.get("PROJECT13_OPERATION", "SUM_RANGE")
TASK_ENABLED = os.environ.get("PROJECT13_TASK_ENABLED", "0") == "1"
TASK_START = read_int("PROJECT13_TASK_START", 1)
TASK_END = read_int("PROJECT13_TASK_END", 1000)
REQUIRED_NODES = read_int("PROJECT13_REQUIRED_NODES", 10)
TOTAL_ROUNDS = read_int("PROJECT13_SUBTASK_COUNT", 5)

INITIAL_REPUTATION = 60
CORRECT_REWARD = 5
WRONG_PENALTY = 15
MALICIOUS_WRONG_ROUNDS = 5
IMPORTANT_TASK_MIN_REPUTATION = 60

# 演示环境在首次运行时生成节点独立密钥，密钥只写入凭据文件，
# 不写进源码和日志。许可证有效期贼长
DEMO_CREDENTIAL_COUNT = 50
LICENSE_EXPIRES = "2030-12-31"

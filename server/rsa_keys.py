"""首次部署生成 RSA-2048 任务签名密钥，私钥只保存在服务端。"""

import json
import math
import secrets
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRIVATE_KEY_FILE = PROJECT_ROOT / "data" / "task_private_key.json"
PUBLIC_KEY_FILE = PROJECT_ROOT / "client" / "task_public.key"
PUBLIC_EXPONENT = 65537


def _probably_prime(number, rounds=24):
    if number < 2 or number % 2 == 0:
        return number == 2
    d = number - 1
    power = 0
    while d % 2 == 0:
        d //= 2
        power += 1
    for _ in range(rounds):
        base = secrets.randbelow(number - 3) + 2
        value = pow(base, d, number)
        if value in (1, number - 1):
            continue
        for _ in range(power - 1):
            value = pow(value, 2, number)
            if value == number - 1:
                break
        else:
            return False
    return True


def _generate_prime(bit_count):
    while True:
        candidate = secrets.randbits(bit_count)
        candidate |= (1 << (bit_count - 1)) | 1
        if math.gcd(candidate - 1, PUBLIC_EXPONENT) == 1:
            if _probably_prime(candidate):
                return candidate


def ensure_task_signing_keys():
    if PRIVATE_KEY_FILE.exists() and PUBLIC_KEY_FILE.exists():
        try:
            record = json.loads(PRIVATE_KEY_FILE.read_text(encoding="ascii"))
            if "first_prime" in record and "second_prime" in record:
                return
        except (OSError, json.JSONDecodeError):
            pass

    first_prime = _generate_prime(1024)
    second_prime = _generate_prime(1024)
    while (
        second_prime == first_prime
        or (first_prime * second_prime).bit_length() != 2048
    ):
        second_prime = _generate_prime(1024)
    modulus = first_prime * second_prime
    private_exponent = pow(
        PUBLIC_EXPONENT, -1,
        (first_prime - 1) * (second_prime - 1)
    )

    PRIVATE_KEY_FILE.parent.mkdir(exist_ok=True)
    PRIVATE_KEY_FILE.write_text(json.dumps({
        "modulus": format(modulus, "x"),
        "public_exponent": PUBLIC_EXPONENT,
        "private_exponent": format(private_exponent, "x"),
        "first_prime": format(first_prime, "x"),
        "second_prime": format(second_prime, "x"),
    }, indent=2), encoding="ascii")
    PUBLIC_KEY_FILE.write_text(
        "PROJECT13-RSA-PUBLIC-V1\n"
        f"modulus={format(modulus, 'x')}\n"
        f"public_exponent={PUBLIC_EXPONENT}\n",
        encoding="ascii",
    )


def read_private_key():
    ensure_task_signing_keys()
    record = json.loads(PRIVATE_KEY_FILE.read_text(encoding="ascii"))
    return (
        int(record["modulus"], 16),
        int(record["public_exponent"]),
        int(record["private_exponent"], 16),
        int(record["first_prime"], 16),
        int(record["second_prime"], 16),
    )

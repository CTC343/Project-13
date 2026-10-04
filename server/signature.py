"""使用 RSA-2048 和 SHA-256/PKCS#1 v1.5 签名任务水印。"""

import hashlib

from rsa_keys import read_private_key


SHA256_DIGEST_INFO_PREFIX = bytes.fromhex(
    "3031300d060960864801650304020105000420"
)


def text_checksum(text):
    """保留给性能评估使用的快速摘要接口。"""
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest(), "big")


def sign_task(task_text):
    modulus, _, private_exponent, first_prime, second_prime = read_private_key()
    key_size = (modulus.bit_length() + 7) // 8
    digest_info = SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(
        task_text.encode("utf-8")
    ).digest()
    padding_size = key_size - len(digest_info) - 3
    if padding_size < 8:
        raise ValueError("RSA key is too small for SHA-256 signature")
    encoded = b"\x00\x01" + b"\xff" * padding_size + b"\x00" + digest_info
    message = int.from_bytes(encoded, "big")
    first_result = pow(
        message, private_exponent % (first_prime - 1), first_prime
    )
    second_result = pow(
        message, private_exponent % (second_prime - 1), second_prime
    )
    coefficient = pow(second_prime, -1, first_prime)
    signature = second_result + second_prime * (
        (first_result - second_result) * coefficient % first_prime
    )
    return signature.to_bytes(key_size, "big").hex()

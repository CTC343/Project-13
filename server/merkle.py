"""验证四个计算步骤及其 Merkle Tree 根哈希。"""

import hashlib

from operations import merge_values


def hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_merkle_root(step_values):
    leaf_hashes = [hash_text(str(value)) for value in step_values]
    left_hash = hash_text(leaf_hashes[0] + leaf_hashes[1])
    right_hash = hash_text(leaf_hashes[2] + leaf_hashes[3])
    return hash_text(left_hash + right_hash)


def verify_result_proof(operation, result_value, proof_text, expected_root):
    try:
        step_values = [int(value) for value in proof_text.split(",")]
    except ValueError:
        return False

    if len(step_values) != 4:
        return False
    if merge_values(operation, step_values) != result_value:
        return False

    return build_merkle_root(step_values) == expected_root

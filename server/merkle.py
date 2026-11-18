"""验证四个计算步骤及其 Merkle Tree 根哈希。"""

import hashlib

from operations import merge_values


# 计算 Merkle 节点使用的 SHA-256 摘要。
def hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# 将四段结果逐层哈希，重新计算 Merkle 根。
def build_merkle_root(step_values):
    # 客户端固定提交 4 段；两两合并恰好形成两层父节点和一个根。
    leaf_hashes = [hash_text(str(value)) for value in step_values]
    left_hash = hash_text(leaf_hashes[0] + leaf_hashes[1])
    right_hash = hash_text(leaf_hashes[2] + leaf_hashes[3])
    return hash_text(left_hash + right_hash)


# 检查分段结果、总结果和 Merkle 根是否相互一致。
def verify_result_proof(operation, result_value, proof_text, expected_root):
    try:
        step_values = [int(value) for value in proof_text.split(",")]
    except ValueError:
        return False

    # 固定要求 4 项，和客户端分段数一致，拒绝缺项或额外数据。
    if len(step_values) != 4:
        return False
    if merge_values(operation, step_values) != result_value:
        return False

    return build_merkle_root(step_values) == expected_root

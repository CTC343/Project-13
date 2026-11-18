"""按信誉分筛选可以接收重要任务的节点。"""

from config import IMPORTANT_TASK_MIN_REPUTATION


def choose_important_task_nodes(reputation_scores, malicious_nodes):
    eligible_nodes = []

    for node_id, score in reputation_scores.items():
        # 信誉必须达到配置阈值，且不能已被识别为恶意节点。
        if score >= IMPORTANT_TASK_MIN_REPUTATION:
            if node_id not in malicious_nodes:
                eligible_nodes.append(node_id)

    return sorted(eligible_nodes)

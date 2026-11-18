"""把总区间平均拆成五个计算子任务。"""

from config import TASK_END, TASK_START, TOTAL_ROUNDS


def get_subtask_range(round_number):
    # +1 把闭区间两端都计入数量；整数除法将总区间按轮次尽量均分。
    number_count = TASK_END - TASK_START + 1
    start = TASK_START + number_count * (round_number - 1) // TOTAL_ROUNDS
    # 右边界减 1，使本轮不与下一轮重叠，且所有轮次首尾连续。
    end = TASK_START + number_count * round_number // TOTAL_ROUNDS - 1
    return start, end

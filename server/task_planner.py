"""把总区间平均拆成五个计算子任务。"""

from config import TASK_END, TASK_START, TOTAL_ROUNDS


# 按配置的子任务数均分总区间，返回当前轮次负责的起止范围。
def get_subtask_range(round_number, start=None, end=None, rounds=None):
    # +1 把闭区间两端都计入数量；整数除法将总区间按轮次尽量均分。
    lower = TASK_START if start is None else start
    upper = TASK_END if end is None else end
    count = TOTAL_ROUNDS if rounds is None else rounds
    number_count = upper - lower + 1
    start = lower + number_count * (round_number - 1) // count
    # 右边界减 1，使本轮不与下一轮重叠，且所有轮次首尾连续。
    end = lower + number_count * round_number // count - 1
    return start, end

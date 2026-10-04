"""把总区间平均拆成五个计算子任务。"""

from config import TASK_END, TASK_START, TOTAL_ROUNDS


def get_subtask_range(round_number):
    number_count = TASK_END - TASK_START + 1
    start = TASK_START + number_count * (round_number - 1) // TOTAL_ROUNDS
    end = TASK_START + number_count * round_number // TOTAL_ROUNDS - 1
    return start, end

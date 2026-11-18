"""定义任务运算的界面名称、预期结果和跨轮合并规则。"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Operation:
    label: str
    description: str
    calculate: Callable[[int, int], int]
    combine: Callable[[Iterable[int]], int]


def _sum_range(start, end):
    # 闭区间有 end - start + 1 项，按等差数列公式求和。
    return (start + end) * (end - start + 1) // 2


def _count_range(start, end):
    return end - start + 1


# 服务器和控制中心使用同一份定义。新增运算时也要在客户端实现同名运算。
_OPERATIONS = {
    "SUM_RANGE": Operation("区间求和", "把各子任务结果相加", _sum_range, sum),
    "COUNT_RANGE": Operation("区间计数", "把各子任务数量相加", _count_range, sum),
    "MIN_RANGE": Operation("区间最小值", "取各子任务最小值中的最小值", lambda start, end: start, min),
    "MAX_RANGE": Operation("区间最大值", "取各子任务最大值中的最大值", lambda start, end: end, max),
}

OPERATION_OPTIONS = [(code, operation.label, operation.description) for code, operation in _OPERATIONS.items()]


def is_supported(operation):
    return isinstance(operation, str) and operation in _OPERATIONS


def operation_label(operation):
    return _OPERATIONS[operation].label if is_supported(operation) else operation


def _get_operation(operation):
    if not is_supported(operation):
        raise ValueError(f"unsupported operation: {operation}")
    return _OPERATIONS[operation]


def merge_values(operation, values):
    if not values:
        return None
    return _get_operation(operation).combine(values)


def expected_result(operation, start, end):
    return _get_operation(operation).calculate(start, end)

"""集中定义可选择的运算及其结果合并规则。"""


OPERATION_OPTIONS = [
    ("SUM_RANGE", "区间求和", "把各子任务结果相加"),
    ("COUNT_RANGE", "区间计数", "把各子任务数量相加"),
    ("MIN_RANGE", "区间最小值", "取各子任务最小值中的最小值"),
    ("MAX_RANGE", "区间最大值", "取各子任务最大值中的最大值"),
]


def is_supported(operation):
    return any(code == operation for code, _, _ in OPERATION_OPTIONS)


def operation_label(operation):
    for code, label, _ in OPERATION_OPTIONS:
        if code == operation:
            return label
    return operation


def merge_values(operation, values):
    if not values:
        return None

    if operation in ("SUM_RANGE", "COUNT_RANGE"):
        return sum(values)
    if operation == "MIN_RANGE":
        return min(values)
    if operation == "MAX_RANGE":
        return max(values)

    raise ValueError(f"unsupported operation: {operation}")


def expected_result(operation, start, end):
    if operation == "SUM_RANGE":
        number_count = end - start + 1
        return (start + end) * number_count // 2
    if operation == "COUNT_RANGE":
        return end - start + 1
    if operation == "MIN_RANGE":
        return start
    if operation == "MAX_RANGE":
        return end

    raise ValueError(f"unsupported operation: {operation}")

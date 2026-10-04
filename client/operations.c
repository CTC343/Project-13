/* 客户端支持的简单区间运算。网络主流程不关心具体计算方法。 */
#include <string.h>

#include "operations.h"

int is_operation_supported(const char *operation)
{
    return strcmp(operation, "SUM_RANGE") == 0
           || strcmp(operation, "COUNT_RANGE") == 0
           || strcmp(operation, "MIN_RANGE") == 0
           || strcmp(operation, "MAX_RANGE") == 0;
}

long calculate_operation(const char *operation, long start, long end)
{
    long result;
    long number;

    if (strcmp(operation, "SUM_RANGE") == 0) {
        result = 0;
        for (number = start; number <= end; number++) {
            result += number;
        }
        return result;
    }
    if (strcmp(operation, "COUNT_RANGE") == 0) {
        return end - start + 1;
    }
    if (strcmp(operation, "MIN_RANGE") == 0) {
        return start;
    }
    if (strcmp(operation, "MAX_RANGE") == 0) {
        return end;
    }
    return 0;
}

long merge_step_values(const char *operation, long values[4])
{
    long result = values[0];
    int index;

    if (strcmp(operation, "SUM_RANGE") == 0
            || strcmp(operation, "COUNT_RANGE") == 0) {
        for (index = 1; index < 4; index++) {
            result += values[index];
        }
    } else if (strcmp(operation, "MIN_RANGE") == 0) {
        for (index = 1; index < 4; index++) {
            if (values[index] < result) {
                result = values[index];
            }
        }
    } else if (strcmp(operation, "MAX_RANGE") == 0) {
        for (index = 1; index < 4; index++) {
            if (values[index] > result) {
                result = values[index];
            }
        }
    }

    return result;
}

void change_step_for_wrong_test(const char *operation, long values[4])
{
    if (strcmp(operation, "MIN_RANGE") == 0) {
        values[0] += 1;
    } else {
        values[3] += 1;
    }
}

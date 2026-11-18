#ifndef PROJECT13_OPERATIONS_H
#define PROJECT13_OPERATIONS_H

/* 判断任务操作是否属于客户端支持的区间运算。 */
int is_operation_supported(const char *operation);

/* 计算闭区间 [start, end] 的单段结果。 */
long calculate_operation(const char *operation, long start, long end);

/* 按对应运算规则合并四段结果。 */
long merge_step_values(const char *operation, long values[4]);

/* 测试专用：人为改动一段结果以模拟错误节点。 */
void change_step_for_wrong_test(const char *operation, long values[4]);

#endif

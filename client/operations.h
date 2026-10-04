#ifndef PROJECT13_OPERATIONS_H
#define PROJECT13_OPERATIONS_H

int is_operation_supported(const char *operation);
long calculate_operation(const char *operation, long start, long end);
long merge_step_values(const char *operation, long values[4]);
void change_step_for_wrong_test(const char *operation, long values[4]);

#endif

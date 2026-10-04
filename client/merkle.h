#ifndef PROJECT13_MERKLE_H
#define PROJECT13_MERKLE_H

int create_result_proof(const char *operation,
                        long range_start, long range_end,
                        int simulate_wrong_result, long *result,
                        char *proof_steps, int proof_size,
                        char merkle_root[65]);

#endif

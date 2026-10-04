/* 把区间分为四段，并为四个分段结果建立两层 Merkle Tree。 */
#include <stdio.h>

#include "merkle.h"
#include "operations.h"
#include "security.h"

#define STEP_COUNT 4

static int build_merkle_root(long step_sums[STEP_COUNT],
                             char merkle_root[65])
{
    char leaf_hashes[STEP_COUNT][65];
    char pair_hashes[2][65];
    char number_text[32];
    char combined_hashes[130];
    int index;

    for (index = 0; index < STEP_COUNT; index++) {
        snprintf(number_text, sizeof(number_text), "%ld", step_sums[index]);
        if (!sha256_hex(number_text, leaf_hashes[index])) {
            return 0;
        }
    }

    for (index = 0; index < 2; index++) {
        snprintf(combined_hashes, sizeof(combined_hashes), "%s%s",
                 leaf_hashes[index * 2], leaf_hashes[index * 2 + 1]);
        if (!sha256_hex(combined_hashes, pair_hashes[index])) {
            return 0;
        }
    }

    snprintf(combined_hashes, sizeof(combined_hashes), "%s%s",
             pair_hashes[0], pair_hashes[1]);
    return sha256_hex(combined_hashes, merkle_root);
}

int create_result_proof(const char *operation,
                        long range_start, long range_end,
                        int simulate_wrong_result, long *result,
                        char *proof_steps, int proof_size,
                        char merkle_root[65])
{
    long step_sums[STEP_COUNT];
    long number_count = range_end - range_start + 1;
    long step_start;
    long step_end;
    int index;

    if (result == NULL || proof_steps == NULL || proof_size <= 0) {
        return 0;
    }

    for (index = 0; index < STEP_COUNT; index++) {
        step_start = range_start + number_count * index / STEP_COUNT;
        step_end = range_start + number_count * (index + 1) / STEP_COUNT - 1;
        step_sums[index] = calculate_operation(
            operation, step_start, step_end
        );
    }

    if (simulate_wrong_result) {
        change_step_for_wrong_test(operation, step_sums);
    }

    *result = merge_step_values(operation, step_sums);

    snprintf(proof_steps, proof_size, "%ld,%ld,%ld,%ld",
             step_sums[0], step_sums[1], step_sums[2], step_sums[3]);
    return build_merkle_root(step_sums, merkle_root);
}

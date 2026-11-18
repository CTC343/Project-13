/* 把区间分为四段，并为四个分段结果建立两层 Merkle Tree。 */
#include <stdio.h>

#include "merkle.h"
#include "operations.h"
#include "security.h"

#define STEP_COUNT 4

/* 将四段结果逐层哈希，生成 Merkle 根。 */
static int build_merkle_root(long step_sums[STEP_COUNT],
                             char merkle_root[65])
{
    char leaf_hashes[STEP_COUNT][65];
    char pair_hashes[2][65];
    char number_text[32];
    char combined_hashes[130];
    int index;

    /* 叶节点先对每段结果的十进制文本做哈希，得到固定长度摘要。 */
    for (index = 0; index < STEP_COUNT; index++) {
        snprintf(number_text, sizeof(number_text), "%ld", step_sums[index]);
        if (!sha256_hex(number_text, leaf_hashes[index])) {
            return 0;
        }
    }

    /* 两两拼接相邻叶摘要并哈希，形成第一层父节点。 */
    for (index = 0; index < 2; index++) {
        snprintf(combined_hashes, sizeof(combined_hashes), "%s%s",
                 leaf_hashes[index * 2], leaf_hashes[index * 2 + 1]);
        if (!sha256_hex(combined_hashes, pair_hashes[index])) {
            return 0;
        }
    }

    /* 再合并两个父节点，得到代表全部四段结果的 Merkle 根。 */
    snprintf(combined_hashes, sizeof(combined_hashes), "%s%s",
             pair_hashes[0], pair_hashes[1]);
    return sha256_hex(combined_hashes, merkle_root);
}

/* 生成总结果、四段结果和 Merkle 根，供提交结果时使用。 */
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

    /* 用整数边界把闭区间均匀切成四段，避免逐个传输所有计算明细。 */
    for (index = 0; index < STEP_COUNT; index++) {
        step_start = range_start + number_count * index / STEP_COUNT;
        step_end = range_start + number_count * (index + 1) / STEP_COUNT - 1;
        step_sums[index] = calculate_operation(
            operation, step_start, step_end
        );
    }

    /* 测试路径故意改动一段结果，用来验证错误结果能否被发现。 */
    if (simulate_wrong_result) {
        change_step_for_wrong_test(operation, step_sums);
    }

    /* 汇总值、可读的分段值和 Merkle 根均基于同一组分段结果生成。 */
    *result = merge_step_values(operation, step_sums);

    snprintf(proof_steps, proof_size, "%ld,%ld,%ld,%ld",
             step_sums[0], step_sums[1], step_sums[2], step_sums[3]);
    return build_merkle_root(step_sums, merkle_root);
}

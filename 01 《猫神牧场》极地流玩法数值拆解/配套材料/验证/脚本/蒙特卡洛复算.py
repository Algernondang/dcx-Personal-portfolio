"""复现《猫神牧场》极地流的两组出手顺序实验。仅依赖 Python 标准库。"""

import argparse
import csv
from pathlib import Path
from tempfile import NamedTemporaryFile

SEED = 20260828
ORDER_SEED = 96408241
TRIALS = 1000
TURNS = 30
MASK = (1 << 32) - 1
HEADERS = [
    "阵容组数x", "回合t", "模拟次数", "冻结所需命中", "平均首轮雪球数",
    "平均累计雪球数", "平均触发轮数", "P10触发轮数", "P50触发轮数",
    "P90触发轮数", "进入第二轮比例", "平均冻结覆盖率",
    "整回合全体至少冻结一次比例", "首轮全冻比例", "全轮满冻结比例",
    "出手顺序", "首轮最大单只雪球占比均值",
]


def rng32(seed):
    """生成 Mulberry32 无符号整数序列。"""
    state = seed & MASK
    while True:
        state = (state + 0x6D2B79F5) & MASK
        value = ((state ^ (state >> 15)) * (state | 1)) & MASK
        value ^= (value + ((value ^ (value >> 7)) * (value | 61))) & MASK
        yield (value ^ (value >> 14)) & MASK


def simulate_turn(x, snowballs, draws, order_draws=None):
    """每轮从无冻结开始。最后一轮未解冻的状态在回合交界重置。"""
    animals = 2 * x
    active = list(range(x))
    initial = sum(snowballs)
    total = rounds = covered = 0
    first_full = False
    all_rounds_full = True
    while active and rounds < x + 1:
        rounds += 1
        if order_draws is not None:
            for j in range(len(active) - 1, 0, -1):
                k = (next(order_draws) * (j + 1)) >> 32
                active[j], active[k] = active[k], active[j]
        hits = [0] * animals
        frozen = 0
        for penguin in active:
            amount = snowballs[penguin]
            total += amount
            for _ in range(amount):
                # 此轮全体已冻结后，剩余雪球只计发射数，并跳过抽样。
                if frozen == (1 << animals) - 1:
                    break
                target = (next(draws) * (animals - 1)) >> 32
                if target >= penguin:
                    target += 1
                hits[target] += 1
                if hits[target] == 2:
                    frozen |= 1 << target
                    snowballs[penguin] += 1
        covered |= frozen
        full = frozen == (1 << animals) - 1
        if rounds == 1:
            first_full = full
        all_rounds_full &= full
        # 猛犸象解冻后，所有刚被冻住的企鹅都可以再次触发。
        active = [penguin for penguin in range(x) if frozen & (1 << penguin)]
    return (initial, total, rounds, int(rounds > 1), covered.bit_count(),
            int(covered == (1 << animals) - 1), int(first_full),
            int(all_rounds_full and rounds == x + 1))


def simulate_group(x, turns=TURNS, trials=TRIALS, *, random_order=True, seed=SEED):
    samples = [[] for _ in range(turns)]
    draws = rng32(seed + x * 100000)
    order_seed = seed + (ORDER_SEED - SEED) + x * 100000
    order_draws = rng32(order_seed) if random_order else None
    order_name = "每轮随机" if random_order else "固定顺序"
    for _ in range(trials):
        snowballs = [5] * x
        for sample in samples:
            share = max(snowballs) / sum(snowballs)
            sample.append((*simulate_turn(x, snowballs, draws, order_draws), share))
    for turn, sample in enumerate(samples, start=1):
        totals = [sum(column) for column in zip(*sample)]
        ranks = sorted(row[2] for row in sample)
        quantiles = [ranks[(trials - 1) * p // 10] for p in (1, 5, 9)]
        yield [x, turn, trials, 2, totals[0] / trials, totals[1] / trials,
               totals[2] / trials, *quantiles, totals[3] / trials,
               totals[4] / (trials * 2 * x), *(value / trials for value in totals[5:8]),
               order_name, totals[8] / trials]


def write_table(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="",
                                dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    data_dir = Path(__file__).resolve().parents[1] / "数据"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups", type=int, choices=range(2, 7),
                        help="只计算指定阵容，省略时计算 2 至 6 组。")
    parser.add_argument("--trials", type=int, default=TRIALS, help="每种顺序的轨迹数。")
    parser.add_argument("--seed", type=int, default=SEED, help="命中种子的基数。")
    parser.add_argument("--output", type=Path, help="对照表路径。指定时仅输出对照表。")
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("轨迹数须为正整数。")
    if not 0 <= args.seed <= MASK:
        parser.error("命中种子须为 0 至 4,294,967,295 的整数。")

    original_setting = args.groups is None and args.trials == TRIALS and args.seed == SEED
    default_output = (data_dir / "极地流_出手顺序对照.csv" if original_setting
                      else Path("极地流_出手顺序_试算.csv"))
    lineup = (args.groups,) if args.groups is not None else range(2, 7)
    comparison = []
    for random_order in (True, False):
        for x in lineup:
            rows = list(simulate_group(x, trials=args.trials, random_order=random_order, seed=args.seed))
            comparison.extend(rows)
            print(f"{rows[0][15]} · {x} 组 · {args.trials} 条 {TURNS} 回合轨迹", flush=True)

    write_table(args.output or default_output, HEADERS, comparison)
    if original_setting and args.output is None:
        fixed = (row[:15] for row in comparison if row[15] == "固定顺序")
        write_table(data_dir / "极地流_固定顺序.csv", HEADERS[:15], fixed)


if __name__ == "__main__":
    main()

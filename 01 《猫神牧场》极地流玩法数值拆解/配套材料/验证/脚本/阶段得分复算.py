"""按完整冻结口径复算极地流得分。Python 3.10+，仅使用标准库。"""

import argparse
import csv
from itertools import islice
from math import factorial
from pathlib import Path

SCHEMES = ("原版", "策划改版", "每5层方案", "每10层方案")
ROUNDS_PER_STAGE = 10
BASE_QUOTA = 36_000


def round_records(groups, stages):
    """按轮次递推基础分，逐轮换算脂肪，返回整数得分。"""
    total_fat = 0
    mammoths = [20] * groups
    for turn in range(1, stages * ROUNDS_PER_STAGE + 1):
        base_score = 0
        for i in range(groups):
            triggers = (turn - 1) * (groups + 1) + i + 1
            freeze = 5 * groups + 2 * groups * (triggers - 1) - 2 * groups
            total_fat += freeze // 5
            mammoths[i] += freeze
            # 每只猛犸象与企鹅均随已发生的冻结获得基础分。
            base_score += 2 * (sum(mammoths) + groups * (2 + 2 * triggers))
        five = total_fat // (10 * groups)
        ten = total_fat // (20 * groups)
        multipliers = (1 << ten, 1 << ((five + 1).bit_length() - 1),
                       max(1, 2 * five), max(1, 2 * ten))
        yield turn, total_fat, base_score, tuple(base_score * m for m in multipliers)


def stage_records(groups, stages):
    rounds = iter(round_records(groups, stages))
    for stage in range(1, stages + 1):
        scores = [r[3] for r in islice(rounds, ROUNDS_PER_STAGE)]
        yield stage, BASE_QUOTA * factorial(stage), tuple(map(sum, zip(*scores)))


def ratio_text(numerator, denominator, digits=6):
    """仅显示时截取有效数字，保留超出浮点范围的比值。"""
    if numerator <= 0 or denominator <= 0:
        raise ValueError("正分数和正阈值才可转换为科学计数法")
    from decimal import Decimal, localcontext
    with localcontext() as ctx:
        ctx.prec = digits + 8
        return format(Decimal(numerator) / Decimal(denominator), f".{digits - 1}E")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups", type=int, choices=range(2, 16), default=5,
                        metavar="2–15")
    parser.add_argument("--stages", type=int, choices=range(1, 31), default=15,
                        metavar="1–30")
    parser.add_argument("--output", type=Path, help="输出阶段阈值、得分比和达标状态的 CSV。")
    args = parser.parse_args()
    rows = []
    first_failed = [None] * len(SCHEMES)
    for stage, quota, scores in stage_records(args.groups, args.stages):
        for i, score in enumerate(scores):
            if first_failed[i] is None and score < quota:
                first_failed[i] = stage
        rows.append([stage, quota, *(ratio_text(score, quota) for score in scores),
                     *("达标" if score >= quota else "未达标" for score in scores)])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["无尽阶段", "上贡阈值", *(f"{name}得分/阈值" for name in SCHEMES),
                             *(f"{name}阶段状态" for name in SCHEMES)])
            writer.writerows(rows)
    for name, stage in zip(SCHEMES, first_failed):
        result = f"第 {stage} 阶段" if stage else f"前 {args.stages} 阶段均达标"
        print(f"{name} · 首次未达标 · {result}")


if __name__ == "__main__":
    main()

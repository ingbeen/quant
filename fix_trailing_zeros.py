#!/usr/bin/env python3
"""
불필요한 trailing zeros를 제거하는 스크립트
"""
import csv
from pathlib import Path
from decimal import Decimal


def remove_trailing_zeros(backup_path: Path, output_path: Path) -> None:
    """
    backup CSV 파일을 읽어서 정확한 소수점 변환 후 trailing zeros 제거하여 저장

    Args:
        backup_path: 원본 백업 파일 경로
        output_path: 수정된 파일을 저장할 경로
    """
    rows = []

    with open(backup_path, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows.append(header)

        for row in reader:
            if len(row) == 2:
                date, value = row
                # Decimal을 사용하여 정확한 계산
                decimal_value = Decimal(value) / Decimal('100')
                # normalize()로 trailing zeros 제거
                normalized_value = decimal_value.normalize()
                rows.append([date, str(normalized_value)])
            else:
                # 빈 행은 그대로 유지
                rows.append(row)

    # 수정된 내용 저장
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"✓ {output_path.name} 수정 완료")


def main():
    etc_dir = Path('/home/yblee/workspace/quant/storage/etc')

    # federal_funds_rate_monthly.csv 수정
    remove_trailing_zeros(
        etc_dir / 'federal_funds_rate_monthly.csv.backup',
        etc_dir / 'federal_funds_rate_monthly.csv'
    )

    # tqqq_net_expense_ratio_monthly.csv 수정
    remove_trailing_zeros(
        etc_dir / 'tqqq_net_expense_ratio_monthly.csv.backup',
        etc_dir / 'tqqq_net_expense_ratio_monthly.csv'
    )


if __name__ == '__main__':
    main()

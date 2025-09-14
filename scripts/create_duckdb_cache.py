#!/usr/bin/env python3
"""
DuckDB 캐시 생성 및 관리 스크립트

Usage:
    python scripts/create_duckdb_cache.py data/raw/QQQ_max.csv
    python scripts/create_duckdb_cache.py --rebuild-all
"""

import argparse
from pathlib import Path
import pandas as pd
import duckdb


class DuckDBManager:
    """DuckDB 캐시 데이터베이스 관리자"""

    def __init__(self, db_path: str = "cache/market_data.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None

    def connect(self):
        """데이터베이스 연결"""
        if self.conn is None:
            try:
                self.conn = duckdb.connect(str(self.db_path))
                print(f"[CONN] DuckDB 연결: {self.db_path}")
            except duckdb.IOException as e:
                print(f"[ERROR] DuckDB 연결 실패: {e}")
                raise

    def disconnect(self):
        """데이터베이스 연결 해제"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def create_stocks_table(self):
        """주식 데이터를 위한 테이블 생성"""
        self.connect()

        if self.conn is None:
            raise RuntimeError("Database connection not established")

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS stocks (
            symbol VARCHAR NOT NULL,
            date DATE NOT NULL,
            open DECIMAL(10,2),
            close DECIMAL(10,2),
            volume BIGINT,
            PRIMARY KEY (symbol, date)
        );
        """

        self.conn.execute(create_table_sql)
        print("[TABLE] stocks 테이블 생성 완료")

    def import_csv_to_table(self, csv_path: Path) -> str:
        """CSV 파일을 DuckDB 테이블로 import"""
        self.connect()

        if self.conn is None:
            raise RuntimeError("Database connection not established")

        # CSV 파일명에서 심볼 추출
        symbol = csv_path.stem.split("_")[0].upper()

        print(f"[IMPORT] CSV 임포트 중: {csv_path} -> {symbol}")

        # CSV 파일 읽기 및 데이터 정제
        df = pd.read_csv(csv_path)

        # 컬럼명 표준화
        column_mapping = {
            "Date": "date",
            "Open": "open",
            "Close": "close",
            "Volume": "volume",
        }

        df = df.rename(columns=column_mapping)
        df["symbol"] = symbol

        # 필요한 컬럼만 선택
        required_columns = [
            "symbol",
            "date",
            "open",
            "close",
            "volume",
        ]

        df = df[required_columns]

        # 날짜 형식 변환
        df["date"] = pd.to_datetime(df["date"]).dt.date

        # 중복 제거 (같은 심볼, 날짜의 기존 데이터 삭제)
        delete_sql = f"DELETE FROM stocks WHERE symbol = '{symbol}'"
        self.conn.execute(delete_sql)

        # 데이터 삽입
        self.conn.execute("INSERT INTO stocks SELECT * FROM df")

        row_count = len(df)
        date_range = f"{df['date'].min()} ~ {df['date'].max()}"

        print(f"[SUCCESS] {symbol} 데이터 임포트 완료: {row_count:,}행, {date_range}")

        return symbol


def process_csv_file(csv_path: Path, db_manager: DuckDBManager) -> bool:
    """단일 CSV 파일을 DuckDB로 처리하는 공통 함수"""
    try:
        db_manager.create_stocks_table()
        db_manager.import_csv_to_table(csv_path)
        return True
    except Exception as e:
        print(f"[ERROR] {csv_path} 처리 중 오류: {e}")
        return False


def rebuild_cache_from_csv_files(csv_dir: str = "data/raw"):
    """CSV 파일들로부터 DuckDB 캐시 재구성"""
    csv_path = Path(csv_dir)

    if not csv_path.exists():
        print(f"[ERROR] CSV 디렉토리가 존재하지 않습니다: {csv_path}")
        return

    csv_files = list(csv_path.glob("*.csv"))

    if not csv_files:
        print(f"[INFO] CSV 파일이 없습니다: {csv_path}")
        return

    print(f"[INFO] CSV 파일들로부터 DuckDB 캐시 재구성 중...")
    print(f"[INFO] 경로: {csv_path}")
    print(f"[INFO] 파일 수: {len(csv_files)}")

    with DuckDBManager() as db:
        for csv_file in csv_files:
            process_csv_file(csv_file, db)

        print(f"\n[SUCCESS] 캐시 재구성 완료!")


def main():
    parser = argparse.ArgumentParser(description="DuckDB 캐시 관리")
    parser.add_argument("csv_file", nargs="?", help="가져올 CSV 파일 경로")
    parser.add_argument(
        "--rebuild-all", action="store_true", help="data/raw의 모든 CSV로 캐시 재구성"
    )

    args = parser.parse_args()

    if args.rebuild_all:
        rebuild_cache_from_csv_files()
        return 0

    db_manager = DuckDBManager()

    if args.csv_file:
        csv_path = Path(args.csv_file)

        if not csv_path.exists():
            print(f"[ERROR] CSV 파일이 존재하지 않습니다: {csv_path}")
            return 1

        with db_manager:
            success = process_csv_file(csv_path, db_manager)
            if success:
                print(f"\n[SUCCESS] 임포트 완료!")
                return 0
            else:
                return 1
    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    exit(main())

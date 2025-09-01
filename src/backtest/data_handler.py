"""
Data Handler - 데이터 로딩 및 처리

DuckDB에서 데이터를 읽어오고 백테스팅에 필요한 형태로 가공
"""

from typing import Optional, List, Dict, Union, Tuple, Any
from datetime import date
from pathlib import Path
import pandas as pd
import duckdb
from decimal import Decimal


class DataHandler:
    """데이터 처리 클래스"""

    def __init__(self, db_path: str = "cache/market_data.db"):
        """
        Args:
            db_path: DuckDB 데이터베이스 파일 경로
        """
        self.db_path = Path(db_path)
        self.conn: Optional[duckdb.DuckDBPyConnection] = None

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"데이터베이스 파일이 없습니다: {self.db_path}\n"
                f"다음 명령어로 데이터베이스를 생성하세요:\n"
                f"python scripts/create_duckdb_cache.py --rebuild-all"
            )

    def __enter__(self) -> "DataHandler":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.disconnect()

    def connect(self) -> None:
        """데이터베이스 연결"""
        if self.conn is None:
            self.conn = duckdb.connect(str(self.db_path))

    def disconnect(self) -> None:
        """데이터베이스 연결 해제"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_available_symbols(self) -> List[str]:
        """사용 가능한 심볼 목록 조회"""
        self.connect()

        if self.conn is None:
            raise RuntimeError("Database connection not established")

        try:
            result = self.conn.execute(
                """
                SELECT DISTINCT symbol 
                FROM stocks 
                ORDER BY symbol
            """
            ).fetchall()

            return [row[0] for row in result]

        except Exception as e:
            print(f"심볼 목록 조회 실패: {e}")
            return []

    def get_symbol_date_range(
        self, symbol: str
    ) -> Tuple[Optional[date], Optional[date]]:
        """심볼의 데이터 기간 조회"""
        self.connect()

        if self.conn is None:
            raise RuntimeError("Database connection not established")

        try:
            result = self.conn.execute(
                """
                SELECT MIN(date) as start_date, MAX(date) as end_date
                FROM stocks 
                WHERE symbol = ?
            """,
                [symbol],
            ).fetchone()

            if result and result[0] and result[1]:
                return result[0], result[1]
            else:
                return None, None

        except Exception as e:
            print(f"날짜 범위 조회 실패: {e}")
            return None, None

    def load_stock_data(
        self,
        symbol: str,
        start_date: Optional[Union[str, date]] = None,
        end_date: Optional[Union[str, date]] = None,
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        주식 데이터 로드

        Args:
            symbol: 주식 심볼
            start_date: 시작 날짜
            end_date: 종료 날짜
            columns: 가져올 컬럼 리스트 (None이면 모든 컬럼)

        Returns:
            주식 데이터 DataFrame
        """
        self.connect()

        # 컬럼 선택
        if columns:
            column_str = ", ".join(columns)
        else:
            column_str = "*"

        # WHERE 절 구성
        where_conditions = ["symbol = ?"]
        params: List[Union[str, date]] = [symbol]

        if start_date:
            where_conditions.append("date >= ?")
            params.append(start_date)

        if end_date:
            where_conditions.append("date <= ?")
            params.append(end_date)

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT {column_str}
        FROM stocks 
        WHERE {where_clause}
        ORDER BY date ASC
        """

        if self.conn is None:
            raise RuntimeError("Database connection not established")

        try:
            df = self.conn.execute(query, params).fetchdf()

            if df.empty:
                print(
                    f"[WARNING] 데이터가 없습니다: {symbol} ({start_date} ~ {end_date})"
                )
                return df

            # 날짜 컬럼을 datetime으로 변환 (있는 경우)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])

            return df

        except Exception as e:
            print(f"데이터 로드 실패: {e}")
            return pd.DataFrame()

    def load_multiple_symbols(
        self,
        symbols: List[str],
        start_date: Optional[Union[str, date]] = None,
        end_date: Optional[Union[str, date]] = None,
        column: str = "close",
    ) -> pd.DataFrame:
        """
        여러 심볼의 데이터를 한번에 로드 (pivot 형태)

        Args:
            symbols: 심볼 리스트
            start_date: 시작 날짜
            end_date: 종료 날짜
            column: 가져올 컬럼 (기본: close)

        Returns:
            각 심볼을 컬럼으로 하는 pivot 테이블
        """
        self.connect()

        # WHERE 절 구성
        symbol_placeholders = ",".join(["?" for _ in symbols])
        where_conditions = [f"symbol IN ({symbol_placeholders})"]
        params: List[Union[str, date]] = list(symbols)

        if start_date:
            where_conditions.append("date >= ?")
            params.append(start_date)

        if end_date:
            where_conditions.append("date <= ?")
            params.append(end_date)

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT date, symbol, {column}
        FROM stocks 
        WHERE {where_clause}
        ORDER BY date ASC, symbol ASC
        """

        if self.conn is None:
            raise RuntimeError("Database connection not established")

        try:
            df = self.conn.execute(query, params).fetchdf()

            if df.empty:
                return df

            # pivot 테이블로 변환
            pivot_df = df.pivot(index="date", columns="symbol", values=column)
            pivot_df.index = pd.to_datetime(pivot_df.index)

            return pivot_df

        except Exception as e:
            print(f"다중 심볼 데이터 로드 실패: {e}")
            return pd.DataFrame()

    def get_price_at_date(
        self, symbol: str, target_date: Union[str, date]
    ) -> Optional[Decimal]:
        """특정 날짜의 종가 조회"""
        self.connect()

        if self.conn is None:
            raise RuntimeError("Database connection not established")

        try:
            result = self.conn.execute(
                """
                SELECT close 
                FROM stocks 
                WHERE symbol = ? AND date = ?
                LIMIT 1
            """,
                [symbol, target_date],
            ).fetchone()

            if result:
                return Decimal(str(result[0]))
            else:
                return None

        except Exception as e:
            print(f"가격 조회 실패: {e}")
            return None

    def get_latest_prices(
        self, symbols: Optional[List[str]] = None
    ) -> Dict[str, Decimal]:
        """최신 가격 조회"""
        self.connect()

        if self.conn is None:
            raise RuntimeError("Database connection not established")

        if symbols:
            symbol_placeholders = ",".join(["?" for _ in symbols])
            where_clause = f"WHERE symbol IN ({symbol_placeholders})"
            params = symbols
        else:
            where_clause = ""
            params = []

        query = f"""
        WITH latest_dates AS (
            SELECT symbol, MAX(date) as latest_date
            FROM stocks 
            {where_clause}
            GROUP BY symbol
        )
        SELECT s.symbol, s.close
        FROM stocks s
        INNER JOIN latest_dates ld ON s.symbol = ld.symbol AND s.date = ld.latest_date
        """

        try:
            result = self.conn.execute(query, params).fetchall()

            return {row[0]: Decimal(str(row[1])) for row in result}

        except Exception as e:
            print(f"최신 가격 조회 실패: {e}")
            return {}

    def calculate_returns(
        self, data: pd.DataFrame, price_column: str = "close"
    ) -> pd.Series:
        """수익률 계산"""
        if data.empty or price_column not in data.columns:
            return pd.Series()

        return data[price_column].pct_change().dropna()

    def resample_data(self, data: pd.DataFrame, frequency: str = "D") -> pd.DataFrame:
        """
        데이터 리샘플링

        Args:
            data: 원본 데이터
            frequency: 리샘플링 주기 ('D': 일별, 'W': 주별, 'M': 월별)
        """
        if data.empty or "date" not in data.columns:
            return data

        data = data.copy()
        data.set_index("date", inplace=True)

        # OHLC 데이터 리샘플링
        agg_dict = {}
        if "open" in data.columns:
            agg_dict["open"] = "first"
        if "high" in data.columns:
            agg_dict["high"] = "max"
        if "low" in data.columns:
            agg_dict["low"] = "min"
        if "close" in data.columns:
            agg_dict["close"] = "last"
        if "volume" in data.columns:
            agg_dict["volume"] = "sum"

        # 기타 컬럼은 마지막 값 사용
        for col in data.columns:
            if col not in agg_dict:
                agg_dict[col] = "last"

        resampled = data.resample(frequency).agg(agg_dict)
        resampled.dropna(inplace=True)

        # 인덱스를 다시 컬럼으로
        resampled.reset_index(inplace=True)

        return resampled

    def validate_data(self, data: pd.DataFrame) -> bool:
        """데이터 유효성 검사"""
        if data.empty:
            print("[ERROR] 데이터가 비어있습니다")
            return False

        required_columns = ["date", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]

        if missing_columns:
            print(f"[ERROR] 필수 컬럼이 없습니다: {missing_columns}")
            return False

        # 중복 날짜 검사
        if data.duplicated(subset=["date"]).any():
            print("[WARNING] 중복된 날짜가 있습니다")

        # 가격 데이터 유효성
        if (data["close"] <= 0).any():
            print("[WARNING] 0 이하의 가격 데이터가 있습니다")

        print(f"[SUCCESS] 데이터 검증 완료: {len(data)}행")
        return True

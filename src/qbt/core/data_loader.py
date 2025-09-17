"""
데이터 로더

DuckDB에서 주식 데이터를 로드하고 메모리 캐싱을 관리합니다.
"""

import pandas as pd
import duckdb
from pathlib import Path
from typing import Optional, Dict, Any, Mapping, Literal
from datetime import datetime
from types import TracebackType

from qbt.types import CacheInfo


class DataLoader:
    """DuckDB 데이터 로더 및 메모리 캐시 관리자"""

    def __init__(self, db_path: str = "cache/market_data.db"):
        """
        데이터 로더 초기화

        Args:
            db_path: DuckDB 데이터베이스 파일 경로
        """
        self.db_path = Path(db_path)
        self._cache: Dict[str, pd.DataFrame] = {}
        self._connection: Optional[duckdb.DuckDBPyConnection] = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """DuckDB 연결 가져오기 (lazy loading)"""
        if self._connection is None:
            if not self.db_path.exists():
                raise FileNotFoundError(
                    f"DuckDB 파일을 찾을 수 없습니다: {self.db_path}"
                )
            self._connection = duckdb.connect(str(self.db_path))
        return self._connection

    def _generate_cache_key(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """캐시 키 생성"""
        return f"{ticker}_{start_date or 'all'}_{end_date or 'all'}"

    def load_data(
        self,
        ticker: str = "QQQ",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        주식 데이터 로드 (메모리 캐시 적용)

        Args:
            ticker: 주식 심볼
            start_date: 시작 날짜 (YYYY-MM-DD 형식)
            end_date: 종료 날짜 (YYYY-MM-DD 형식)

        Returns:
            pd.DataFrame: 주식 데이터
        """
        cache_key = self._generate_cache_key(ticker, start_date, end_date)

        # 캐시에서 먼저 확인
        if cache_key in self._cache:
            print(f"[CACHE] {ticker} 데이터를 캐시에서 로드")
            return self._cache[cache_key].copy()

        # DuckDB에서 데이터 로드
        try:
            conn = self._get_connection()

            # 기본 쿼리 (필요한 컬럼만 선택)
            query = (
                "SELECT ticker, date, open, close, volume FROM stocks WHERE ticker = ?"
            )
            params = [ticker]

            # 날짜 필터 추가
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)

            if end_date:
                query += " AND date <= ?"
                params.append(end_date)

            query += " ORDER BY date ASC"

            print(f"[LOAD] {ticker} 데이터를 DuckDB에서 로드 중...")
            df = conn.execute(query, params).fetchdf()

            if df.empty:
                raise ValueError(f"{ticker}에 대한 데이터를 찾을 수 없습니다.")

            # 데이터 타입 최적화
            df["date"] = pd.to_datetime(df["date"])

            # 수치형 컬럼 처리
            numeric_columns = ["open", "close", "volume"]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # 결측값 확인
            if df.isnull().any().any():
                raise ValueError(
                    f"[ERROR] {ticker} 데이터에 결측값이 발견되었습니다. 스크립트를 중단합니다."
                )

            # 캐시에 저장
            self._cache[cache_key] = df.copy()

            print(f"[LOAD] {ticker} 데이터 로드 완료: {len(df)}개 레코드")
            print(
                f"[LOAD] 기간: {df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')}"
            )

            return df

        except Exception as e:
            print(f"[ERROR] {ticker} 데이터 로드 실패: {e}")
            raise

    def clear_cache(self) -> None:
        """메모리 캐시 초기화"""
        self._cache.clear()
        print("[CACHE] 메모리 캐시를 초기화했습니다.")

    def get_cache_info(self) -> CacheInfo:
        """캐시 정보 반환"""
        cache_size_mb = sum(
            df.memory_usage(deep=True).sum() for df in self._cache.values()
        ) / (1024 * 1024)
        return {
            "cached_datasets": len(self._cache),
            "cache_keys": list(self._cache.keys()),
            "memory_usage_mb": round(cache_size_mb, 2),
        }

    def __enter__(self) -> "DataLoader":
        """Context Manager 진입 시 호출"""
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Literal[False]:
        """Context Manager 종료 시 호출 (예외 발생해도 반드시 실행)"""
        self.close()
        return False  # 예외를 다시 발생시킴

    def close(self) -> None:
        """안전한 리소스 정리"""
        try:
            if self._connection:
                self._connection.close()
                self._connection = None
        except Exception:
            pass  # DB 연결 정리 실패해도 캐시 정리는 계속

        try:
            self.clear_cache()
        except Exception:
            pass  # 캐시 정리 실패해도 계속 진행

        print("[CLEANUP] DataLoader 리소스 정리 완료")

    def __del__(self) -> None:
        """소멸자"""
        self.close()

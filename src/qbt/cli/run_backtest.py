#!/usr/bin/env python3
"""
백테스팅 메인 실행 CLI 모듈

QQQ 데이터로 Buy & Hold 및 Seasonal 전략을 병렬 실행하고 결과를 분석합니다.
"""

from qbt.core.data_loader import DataLoader
from qbt.core.parallel_runner import ParallelRunner
from qbt.strategies.buyandhold import BuyAndHoldStrategy
from qbt.strategies.seasonal import SeasonalStrategy
from qbt.analysis.comparator import StrategyComparator
from datetime import datetime


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print(" QQQ 백테스팅 시스템")
    print("=" * 60)

    try:
        # 1. 데이터 로더 초기화
        print("[1] 데이터 로더 초기화...")
        data_loader = DataLoader("cache/market_data.db")

        # 2. 데이터 로드 (2020-01-01 ~ 2024-12-31)
        print("[2] QQQ 데이터 로드 중...")
        data = data_loader.load_data(
            ticker="QQQ", start_date="2020-01-01", end_date="2024-12-31"
        )

        print(f"    로드된 데이터: {len(data)}개 레코드")
        print(
            f"    기간: {data['date'].min().strftime('%Y-%m-%d')} ~ {data['date'].max().strftime('%Y-%m-%d')}"
        )

        # 데이터 캐시 정보 출력
        cache_info = data_loader.get_cache_info()
        print(
            f"    캐시 상태: {cache_info['cached_datasets']}개 데이터셋, {cache_info['memory_usage_mb']:.1f}MB"
        )

        # 3. 전략 생성
        print("[3] 투자 전략 생성...")
        strategies = [
            BuyAndHoldStrategy(),  # 벤치마크
            SeasonalStrategy(),  # 계절성 전략
        ]

        for strategy in strategies:
            print(f"    - {strategy.name} 전략")

        # 4. 병렬 실행기 초기화
        print("[4] 병렬 실행기 초기화...")
        parallel_runner = ParallelRunner(max_workers=None)  # CPU 코어 수만큼 사용

        # 5. 병렬 백테스팅 실행
        print("[5] 병렬 백테스팅 실행...")
        print("-" * 40)

        results = parallel_runner.run_strategies(
            strategies=strategies, data=data, ticker="QQQ"
        )

        print("-" * 40)

        # 6. 결과 분석
        print("[6] 결과 분석...")

        if not results:
            print("[ERROR] 실행된 전략이 없습니다.")
            return

        # 7. 전략 비교 분석
        print("[7] 전략 비교 분석...")
        comparator = StrategyComparator(results, benchmark_name="BuyAndHold")
        comparison_info = comparator.get_basic_comparison()

        # 8. 결과 출력
        print("[8] 백테스팅 결과 출력")
        parallel_runner.print_summary(results)

        # 9. 상세 결과 출력
        print("\n" + "=" * 60)
        print(" 상세 분석 결과")
        print("=" * 60)

        for strategy_name, result in results.items():
            print(f"\n[{strategy_name}]")
            print(f"  기간: {result['start_date']} ~ {result['end_date']}")
            print(f"  초기 자본: ${result['initial_capital']:,.2f}")
            print(f"  최종 가치: ${result['final_value']:,.2f}")
            print(f"  총 수익률: {result['total_return_pct']:.2f}%")

            if not result.get("is_benchmark", False):
                print(f"  초과 수익률: {result.get('excess_return_pct', 0):.2f}%")

            print(
                f"  총 거래: {result['num_trades']}회 (매수: {result['num_buy_trades']}, 매도: {result['num_sell_trades']})"
            )
            print(f"  승률: {result['win_rate_pct']:.1f}%")
            print(f"  총 수수료: ${result['total_commission']:.2f}")

        # 10. 거래 내역 요약
        print("\n" + "=" * 60)
        print(" 거래 내역 요약")
        print("=" * 60)

        for strategy_name, result in results.items():
            trades = result.get("trades", [])
            if trades:
                print(f"\n[{strategy_name} - 총 {len(trades)}건]")

                # 첫 거래와 마지막 거래만 표시
                if len(trades) >= 1:
                    first_trade = trades[0]
                    print(
                        f"  첫 거래: {first_trade['date']} {first_trade['action']} {first_trade['quantity']:.0f}주 @ ${first_trade['price']:.2f}"
                    )

                if len(trades) >= 2:
                    last_trade = trades[-1]
                    print(
                        f"  마지막: {last_trade['date']} {last_trade['action']} {last_trade['quantity']:.0f}주 @ ${last_trade['price']:.2f}"
                    )

                if len(trades) > 4:  # 중간 거래들이 있는 경우
                    print(f"  ... (중간 {len(trades)-2}건 생략)")
            else:
                print(f"\n[{strategy_name}] 거래 내역 없음")

        # 11. 완료 메시지
        print("\n" + "=" * 60)
        print(" 백테스팅 완료")
        print("=" * 60)
        print(f"  실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  분석 전략: {len(results)}개")
        print(f"  분석 기간: 2020-01-01 ~ 2024-12-31")
        print(f"  총 거래일: {len(data)}일")

        # 12. 벤치마크 대비 성과 요약
        benchmark_result = next(
            (r for r in results.values() if r.get("is_benchmark")), None
        )
        if benchmark_result:
            print(f"\n[벤치마크 대비 성과]")
            benchmark_return = benchmark_result["total_return_pct"]

            for name, result in results.items():
                if not result.get("is_benchmark", False):
                    excess = result.get("excess_return_pct", 0)
                    status = "우수" if excess > 0 else "저조" if excess < 0 else "동일"
                    print(f"  {name}: {status} ({excess:+.2f}%p)")

    except FileNotFoundError as e:
        print(f"[ERROR] 파일을 찾을 수 없습니다: {e}")
        print("다음을 확인해주세요:")
        print("  1. cache/market_data.db 파일 존재 여부")
        print("  2. QQQ 데이터가 DuckDB에 로드되어 있는지 확인")
        print("  3. scripts/create_duckdb_cache.py 실행하여 캐시 생성")

    except Exception as e:
        print(f"[ERROR] 예상치 못한 오류가 발생했습니다: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # 리소스 정리
        try:
            if "data_loader" in locals():
                data_loader.close()
        except:
            pass


if __name__ == "__main__":
    main()
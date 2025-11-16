# QBT (Quant BackTest)

주식 데이터 관리 및 백테스팅을 위한 Python 프레임워크

## 데이터 다운로드

### 기본 사용

```bash
poetry run python main.py download QQQ
```

### 시작 날짜 지정

```bash
poetry run python main.py download SPY --start=2020-01-01
```

### 기간 지정

```bash
poetry run python main.py download AAPL --start=2020-01-01 --end=2023-12-31
```

## 향후 추가 예정

백테스트 실행 등의 기능이 추가될 예정입니다.
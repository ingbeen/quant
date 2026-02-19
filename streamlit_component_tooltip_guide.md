# Streamlit lightweight-charts 커스텀 툴팁 구현 가이드

패키지 포크를 통해 커스텀 툴팁을 구현하는 방법을 정리한다.

## 1. 배경

### 현재 상태

- 패키지: `streamlit-lightweight-charts-v5` v0.1.8
- 내부 라이브러리: `lightweight-charts` v5.1.0 (TradingView)
- 원본 저장소: https://github.com/locupleto/streamlit-lightweight-charts-v5

### 문제

라이브러리 자체는 `subscribeCrosshairMove` + `customValues`를 지원하지만,
Streamlit 컴포넌트의 React 코드(`LightweightChartsComponent.tsx`)에서 이 API를 연결하지 않았다.

### 데이터 흐름

```
app_single_backtest.py (Python)
        |  lightweight_charts_v5_component(charts=[...])
        v
__init__.py (Python 래퍼)
        |  declare_component(path="frontend/build/")
        v
main.f8e5d372.js (JS, 브라우저)
        |  createChart() -> addSeries() -> setData()
        v
lightweight-charts v5.1.0 (Canvas 렌더링)
```

Python dict는 JSON 직렬화를 거쳐 JS로 전달된다.
`customValues` 필드를 포함하면 `setData()`까지 손실 없이 도달한다.

## 2. customValues 메커니즘

lightweight-charts v5.1.0이 이미 지원하는 기능이다.

### 타입

`Record<string, string>` - 값은 문자열만 허용

### Python 측 데이터 예시

```python
{
    "time": "2024-01-15",
    "open": 100.0, "high": 105.0, "low": 98.0, "close": 103.0,
    "customValues": {
        "pct": "1.5",
        "ma": "101.3",
        "upper": "104.3",
        "lower": "98.3"
    }
}
```

### JS 측 접근

```javascript
chart.subscribeCrosshairMove((param) => {
    const data = param.seriesData.get(candleSeries);
    if (data?.customValues) {
        // data.customValues.pct -> "1.5"
        // data.customValues.ma  -> "101.3"
    }
});
```

### 라이브러리 내부 동작

- 입력: 파서(`cu` 래퍼)가 `customValues`를 내부 `Ag` 필드에 저장
- 출력: crosshairMove 콜백의 `seriesData`에서 `customValues`로 복원

## 3. 구현 절차 (패키지 포크)

### 3-1. 포크 및 클론

```bash
# GitHub에서 포크 후 클론
git clone https://github.com/your-org/streamlit-lightweight-charts-v5.git
cd streamlit-lightweight-charts-v5
```

### 3-2. React 소스 수정

대상 파일: `lightweight_charts_v5/frontend/src/LightweightChartsComponent.tsx`

추가할 내용:
1. `subscribeCrosshairMove` 콜백 등록 (차트 생성 직후)
2. tooltip DOM 엘리먼트 생성 + 스타일링
3. cleanup 함수에 `unsubscribeCrosshairMove` 추가

```typescript
// 개념적 코드 (실제 소스 구조에 맞게 조정 필요)

// useEffect 내부, 차트 인스턴스 생성 후:
const tooltip = document.createElement('div');
tooltip.style.cssText = `
    position: absolute; top: 12px; left: 12px; z-index: 10;
    background: rgba(0,0,0,0.85); color: #d1d4dc;
    padding: 8px 12px; border-radius: 4px; font-size: 12px;
    pointer-events: none; display: none;
`;
chartContainer.style.position = 'relative';
chartContainer.appendChild(tooltip);

chart.subscribeCrosshairMove((param) => {
    if (!param.time || !param.seriesData.size) {
        tooltip.style.display = 'none';
        return;
    }
    const candleData = param.seriesData.get(candleSeries);
    if (candleData?.customValues) {
        const cv = candleData.customValues;
        tooltip.innerHTML = [
            cv.pct   ? `전일대비: ${cv.pct}%` : '',
            cv.ma    ? `이평선: ${cv.ma}` : '',
            cv.upper ? `상단밴드: ${cv.upper}` : '',
            cv.lower ? `하단밴드: ${cv.lower}` : '',
        ].filter(Boolean).join('<br>');
        tooltip.style.display = 'block';
    }
});

// cleanup:
// chart.unsubscribeCrosshairMove(handler);
// tooltip.remove();
```

### 3-3. 프론트엔드 빌드

```bash
cd lightweight_charts_v5/frontend
npm install
npm run build    # frontend/build/ 디렉토리 갱신
```

### 3-4. 포크 저장소에 커밋/푸시

```bash
cd ../..
git add .
git commit -m "feat: add custom tooltip with subscribeCrosshairMove + customValues"
git push origin main
```

`frontend/build/` (빌드 결과물)도 함께 커밋한다.
이것이 팀원이 빌드 없이 사용할 수 있는 핵심이다.

### 3-5. 본 프로젝트에서 포크 패키지 참조

```toml
# pyproject.toml
[tool.poetry.dependencies]
streamlit-lightweight-charts-v5 = {
    git = "https://github.com/your-org/streamlit-lightweight-charts-v5.git",
    branch = "main"
}
```

```bash
# 패키지 설치
poetry lock && poetry install
```

### 3-6. Python 앱에서 customValues 전달

```python
# app_single_backtest.py의 _build_candle_data 수정
def _build_candle_data(signal_df, equity_df, ma_col):
    candle_data = []
    for _, row in signal_df.iterrows():
        entry = {
            "time": row[COL_DATE].strftime("%Y-%m-%d"),
            "open": float(row[COL_OPEN]),
            "high": float(row[COL_HIGH]),
            "low": float(row[COL_LOW]),
            "close": float(row[COL_CLOSE]),
        }
        # customValues 추가 (값은 문자열만 허용)
        cv = {}
        if pd.notna(row.get("change_pct")):
            cv["pct"] = f"{row['change_pct']:.2f}"
        if pd.notna(row.get(ma_col)):
            cv["ma"] = f"{row[ma_col]:.2f}"
        if cv:
            entry["customValues"] = cv
        candle_data.append(entry)
    return candle_data
```

## 4. 팀원 공유

### 팀원이 해야 할 것

```bash
git clone https://github.com/your-org/quant.git
cd quant
poetry install    # 포크된 패키지 자동 설치
```

이것만 하면 된다. Node.js도, npm도, 빌드도 필요 없다.

### 이유

- `frontend/build/` (빌드 결과물)이 포크 저장소에 커밋되어 있음
- `poetry install`이 git URL에서 패키지를 가져와 설치
- `poetry.lock`에 커밋 해시가 고정되어 버전 정확히 일치

### 포크 관리자만 하는 것

- React 소스 수정 시 `npm install && npm run build`
- 빌드 결과물을 포크 저장소에 커밋/푸시
- 본 프로젝트에서 `poetry update streamlit-lightweight-charts-v5`

## 5. 업스트림 업데이트 대응

원본 저장소에 새 버전이 나왔을 때:

```bash
cd streamlit-lightweight-charts-v5
git remote add upstream https://github.com/locupleto/streamlit-lightweight-charts-v5.git
git fetch upstream
git merge upstream/main    # 충돌 시 수동 해결
npm install && npm run build
git add . && git commit && git push
```

본 프로젝트에서:

```bash
poetry update streamlit-lightweight-charts-v5
```

## 6. 조사 기준 정보

- 조사일: 2026-02-19
- 컴포넌트 버전: streamlit-lightweight-charts-v5 v0.1.8
- 라이브러리 버전: lightweight-charts v5.1.0
- 원본 저장소: https://github.com/locupleto/streamlit-lightweight-charts-v5

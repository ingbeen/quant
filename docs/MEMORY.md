# MEMORY — 이 저장소에서 알아낸 것

> 작업하며 알아낸 것 중 **모르면 틀리는 것**을 모은다. 함정 · 도메인 사실 · 인계사항 ·
> 작업 규율 · 환경 노하우가 모두 여기 들어간다.
>
> 루트 `CLAUDE.md` 가 `@import` 로 불러오므로 **매 세션 자동으로 읽힌다.** git 으로 추적되어
> 다른 PC 에서도 그대로 보인다 — 그것이 하네스 메모리 대신 이 파일을 쓰는 이유다.
>
> **이미 루트 `CLAUDE.md`·전역 `~/.claude/CLAUDE.md`·`docs/` 문서가 담고 있는 것은 여기 쓰지 않는다.**
> 그쪽도 읽히므로 두 벌이 되고, 한쪽이 낡는다.

## 작업 방식

### 전략 용어는 풀어서 설명한 뒤 결론을 말한다

휩소 · 기회 · 프리미엄 · 버퍼존 · 고원 · WFO 같은 용어를 **연구 문서의 표기 그대로 대화에 꺼내지 않는다.**
`docs/research/` 문서는 용어를 정의해두고 쓰지만, 그 문서를 다시 읽지 않는 한 대화에서는 통하지 않는다.

선택지를 제시할 때는 이 순서로 쓴다 — ① 그 용어가 무엇인지 한 문장 ② 지금 상황의 구체적 숫자 ③ 그래서 무엇을 정해야 하는지. **질문 옵션의 라벨·설명에도 같은 규칙을 적용한다.**

## 개발 환경

### `poetry run` 이 `.venv` 가 아니라 pyenv 를 잡는다 — 에이전트 셸에서만

`poetry run python` 이 `.venv/bin/python` 대신 pyenv 의 파이썬을 실행해 `ModuleNotFoundError: pandas` 가 난다.

**원인은 셸에 들어온 `VIRTUAL_ENV` 다.** Poetry 2.x 는 이미 활성화된 virtualenv 를 존중하므로 `poetry.toml` 의 `in-project = true` 를 무시한다. 그 값은 zsh 프로필이 아니라 **VSCode 의 python-envs 확장이 터미널에 주입**한 것이고, 에이전트 프로세스가 그대로 상속받는다.

```bash
env -u VIRTUAL_ENV poetry run python ...
```

🔴 **저장소 코드를 고칠 문제가 아니고, 사용자에게 환경을 고치라고 요구할 일도 아니다.**
사용자 본인은 `source .venv/bin/activate` 로 쓰며, 그 셸에서는 `VIRTUAL_ENV` 가 `.venv` 를 가리켜 `poetry run` 이 정상 동작한다. **이 문제는 에이전트 셸에서만 발생한다.**

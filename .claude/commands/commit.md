---
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git log:*)
description: 현재 변경사항을 커밋합니다
---

# Git 커밋 명령어

현재 작업 디렉토리의 변경사항을 확인하고 커밋을 생성합니다.

## 작업 순서:
1. 현재 변경사항 확인 (git status, git diff)
2. 최근 커밋 히스토리 확인하여 커밋 메시지 스타일 파악
3. **작업 내용을 기반으로 커밋 메시지 생성 및 사용자에게 확인 요청**
4. **사용자 승인을 기다림 - 승인 전에는 git add나 git commit을 실행하지 않음**
5. 승인 후 변경된 파일들을 스테이징에 추가 (git add)
6. 확인된 메시지로 커밋 실행 (git commit)
7. 커밋 완료 확인 (git status)

## 중요한 규칙:
- **반드시 3-4단계에서 사용자의 명시적 승인을 받은 후에만 git add 및 git commit을 실행합니다**
- **사용자에게 제안 메시지를 보여주고 "이 메시지로 커밋하시겠습니까?"라고 물어봅니다**
- **Claude Code 서명을 절대 포함하지 않습니다 (🤖 Generated with Claude Code, Co-Authored-By: Claude 등)**
- 변경사항이 없으면 빈 커밋을 생성하지 않습니다
- 커밋 메시지는 한국어로 작성하며 간결하게 유지합니다
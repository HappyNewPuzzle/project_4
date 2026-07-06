# 개인용 네이버 블로그 작성 비서

사진과 간단한 리뷰 정보로 네이버 블로그용 초안을 만드는 Python 콘솔
프로그램입니다. ChatGPT 수동 사용, Ollama 로컬 모델, OpenAI API 중
원하는 방식을 선택할 수 있습니다. 자동 로그인이나 자동 게시 기능은
포함하지 않습니다.

## 주요 기능

- 음식점 리뷰와 상품 리뷰 템플릿 분리
- ChatGPT Plus에 직접 붙여넣을 프롬프트 생성 및 클립보드 복사
- Ollama 로컬 Vision 모델을 이용한 무료 글 생성
- OpenAI API를 이용한 Vision 글 생성
- 네이버 스마트에디터에 제목·사진·본문 반자동 배치
- 제목 후보 5개, 본문, 태그 10개 생성
- 결과를 `outputs/generated_posts`에 UTF-8 텍스트 파일로 저장
- ChatGPT용 프롬프트를 `outputs/generated_prompts`에 별도 저장
- `data/settings.json`의 개인 문체 설정을 모든 모드에서 공유
- 입력, 클립보드, Ollama, OpenAI API, 파일 저장 오류 처리

## 폴더 구조

```text
project4/
├── main.py                 # 콘솔 입력과 전체 실행 흐름
├── config.py               # 환경 변수와 settings.json 로드
├── openai_client.py        # 이미지 인코딩과 OpenAI API 호출
├── ollama_client.py        # 로컬 Ollama Vision API 호출
├── clipboard_utils.py      # ChatGPT 프롬프트 클립보드 복사
├── output_schema.py        # 두 AI 제공자가 공유하는 결과 구조
├── naver_automation.py     # Chrome에서 네이버 편집기 반자동 입력
├── post_generator.py       # 입력 검증, 프롬프트 구성, 결과 저장
├── prompts/
│   ├── restaurant_review.txt
│   └── product_review.txt
├── outputs/
│   ├── generated_posts/
│   └── generated_prompts/
├── tests/
│   ├── test_post_generator.py
│   ├── test_ollama_client.py
│   └── test_naver_automation.py
├── data/
│   └── settings.json
├── .env.example
├── requirements.txt
└── README.md
```

## 준비 사항

- Python 3.10 이상
- PNG, JPG/JPEG, WEBP 또는 움직이지 않는 GIF 사진

ChatGPT 수동 모드는 ChatGPT 계정만 있으면 사용할 수 있습니다.
Ollama 모드는 Ollama와 Vision 모델 설치가 필요합니다. OpenAI API
모드만 별도의 API Key와 API 요금이 필요합니다.

## 설치 방법

PowerShell에서 프로젝트 폴더로 이동한 뒤 가상 환경을 만듭니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

선택 설정을 사용하려면 환경 변수 예시 파일을 복사합니다.

```powershell
Copy-Item .env.example .env
```

ChatGPT 수동 모드는 `.env` 없이도 실행됩니다. Ollama 또는 OpenAI
설정을 바꾸려면 생성된 `.env`를 수정합니다. `.env`는 `.gitignore`에
포함되어 저장소에 커밋되지 않습니다.

```dotenv
OPENAI_API_KEY=sk-실제_API_Key
OPENAI_MODEL=gpt-5.4-mini
OLLAMA_MODEL=gemma3:4b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_NUM_CTX=32768
NAVER_WRITE_URL=https://blog.naver.com/GoBlogWrite.naver
```

## 실행 방법과 모드 선택

```powershell
python main.py
```

프로그램을 실행하면 세 가지 방식을 선택할 수 있습니다.

```text
1. ChatGPT용 프롬프트 만들기
2. Ollama 로컬 모델로 글 생성
3. OpenAI API로 글 생성
4. AI 없이 사진·글쓰기 빈 틀 만들기
```

4번은 AI와 GPU를 사용하지 않습니다. 사진을 입력한 순서대로 배치하고 각
사진 뒤에 `✏️ 사진 N 설명을 입력하세요.` 문구를 넣습니다. 네이버 편집기에서
이 안내 문구를 실제 후기 내용으로 바꾸면 되며, 제목 후보·링크·마무리·기본
태그도 즉시 만들어집니다.

입력이 끝나면 `data/last_input.json`에 현재 내용을 임시 저장합니다. 생성,
저장 또는 네이버 배치 중 오류가 나거나 프로그램을 강제로 종료하면 다음
실행에서 이전 입력을 불러올지 묻습니다. 정상 완료되면 임시 입력은 자동으로
삭제되며, 개인 링크와 사진 경로가 담긴 이 파일은 Git에 올라가지 않습니다.

그다음 리뷰 종류, 이름, 링크, 메모와 별점을 입력합니다. Ollama와
OpenAI API 모드에서는 이어서 사진 경로를 입력합니다. ChatGPT 수동
모드는 대화창에서 사진을 직접 첨부하므로 사진 경로를 입력하지 않습니다.
사진을 하나씩 입력하거나 사진들이 들어 있는 폴더 경로를 한 번만 입력할
수 있습니다. 폴더를 입력하면 바로 아래의 PNG, JPG/JPEG, WEBP, GIF
파일을 파일명 숫자 순서대로 모두 추가합니다. 모두 입력한 뒤 빈 줄에서
Enter를 누릅니다. Windows 탐색기의 **경로로 복사** 기능으로 가져온
따옴표 포함 경로도 사용할 수 있습니다.

```text
사진/폴더 1: "C:\Users\사용자\Pictures\리뷰사진"
사진/폴더 11:
```

하위 폴더는 자동으로 탐색하지 않으므로 리뷰별 사진을 한 폴더에 모아두는
방식을 권장합니다.

## 1. ChatGPT Plus 수동 모드

이 모드는 OpenAI API를 호출하지 않으므로 별도 API 요금이 없습니다.
입력 완료 후 다음 작업이 자동으로 처리됩니다.

1. 사진과 리뷰 정보에 맞는 상세 프롬프트를 생성합니다.
2. 프롬프트를 Windows 클립보드에 복사합니다.
3. 프롬프트와 첨부할 사진 목록을 TXT 파일로 저장합니다.

ChatGPT 대화창에 안내된 사진을 모두 첨부하고 `Ctrl+V`로 프롬프트를
붙여넣은 뒤 전송하면 됩니다.

```text
outputs/generated_prompts/YYYYMMDD_HHMMSS_이름_prompt.txt
```

## 2. Ollama 로컬 모드

Ollama 공식 사이트에서 Windows용 Ollama를 설치하고 PowerShell에서
기본 Vision 모델을 내려받습니다.

```powershell
ollama pull gemma3:4b
```

Ollama가 실행 중인 상태에서 `python main.py`를 실행하고 2번을
선택합니다. 사진과 프롬프트는 기본 설정에서 `localhost`의 Ollama로만
전달되며 OpenAI API 요금은 발생하지 않습니다.

PC 메모리가 부족하거나 더 작은 모델을 사용하고 싶다면 `.env`의
`OLLAMA_MODEL`을 설치된 다른 Vision 모델 이름으로 변경할 수 있습니다.
사진이 많아 문맥 크기 오류가 발생하면 `OLLAMA_NUM_CTX`를 조절할 수
있으며, RTX 3060 12GB와 `qwen3.5:9b` 조합의 권장값은 `32768`입니다.

## 3. OpenAI API 모드

`.env`의 `OPENAI_API_KEY`에 실제 API Key를 입력합니다. 이 모드는
ChatGPT Plus와 별도로 API 사용량에 따른 요금이 발생합니다.

생성이 끝나면 결과가 콘솔에 표시되고 다음 위치에 저장됩니다.

```text
outputs/generated_posts/YYYYMMDD_HHMMSS_이름.txt
```

## 네이버 편집기 반자동 배치

Ollama 또는 OpenAI API로 글을 생성한 뒤 다음 질문에 `y`를 입력하면
네이버 편집 자동화를 시작합니다.

```text
네이버 글쓰기 화면에 사진과 본문을 자동 배치할까요? (y/n):
```

1. 제목 후보 5개 중 하나를 선택합니다.
2. 자동화 전용 Chrome 창이 열립니다.
3. 첫 실행에는 브라우저에서 네이버에 직접 로그인합니다.
4. 제목과 본문을 입력할 수 있는 글쓰기 화면이 보이면 콘솔에서 Enter를 누릅니다.
5. 프로그램이 제목, 사진, 해당 사진 설명을 순서대로 배치합니다.
6. 태그 10개는 클립보드에 복사되므로 발행 설정에서 직접 붙여넣습니다.
7. 브라우저에서 사실관계와 배치를 확인한 뒤 임시저장 또는 발행합니다.

프로그램은 계정 비밀번호를 받지 않으며, 로그인 쿠키는 Git에서 제외된
`data/naver_browser_profile`에 저장됩니다. 일반 Chrome 프로필과 충돌하지
않는 전용 프로필입니다.

중요: 프로그램은 발행 버튼을 자동으로 누르지 않습니다. AI가 만든 글에는
사실과 다른 내용이 포함될 수 있으므로 반드시 사용자가 검토해야 합니다.
네이버 스마트에디터 화면 구조가 변경되면 selector를 업데이트해야 할 수
있습니다.

네이버의 공식 블로그 글쓰기 API는 2020년에 종료되었습니다.

```text
https://developers.naver.com/notice/article/7527
```

## 블로그 스타일 바꾸기

`data/settings.json`의 문구를 원하는 말투로 수정하세요. JSON 문법상
각 항목 사이의 쉼표와 큰따옴표는 유지해야 합니다.

글의 전체 구조를 바꾸려면 `prompts/restaurant_review.txt` 또는
`prompts/product_review.txt`를 수정하면 됩니다.

## 오류 해결

- `OPENAI_API_KEY가 없습니다`: `.env` 파일과 Key 값을 확인합니다.
- `사진 파일을 찾을 수 없습니다`: 경로가 정확하고 파일이 존재하는지 확인합니다.
- `Ollama 서버에 연결할 수 없습니다`: Ollama 프로그램이 실행 중인지 확인합니다.
- Ollama HTTP 404 또는 모델 오류: `ollama pull gemma3:4b`를 실행합니다.
- Ollama 문맥 크기 오류: `.env`의 `OLLAMA_NUM_CTX=32768` 설정을 확인합니다.
- Ollama가 제목 5개나 태그 10개를 정확히 만들지 못하면 기존 결과를 버리지 않고 부족한 항목을 자동으로 보충합니다.
- Qwen이 `title` 키나 문단 배열 형태의 `body`를 반환해도 프로그램의 표준 형식으로 자동 변환합니다.
- `OpenAI API 호출에 실패했습니다`: 인터넷 연결, API Key, 사용 한도와 모델 접근 권한을 확인합니다.
- `클립보드에 복사할 수 없습니다`: 저장된 프롬프트 TXT 파일을 직접 복사합니다.
- `스마트에디터 입력 영역을 찾지 못했습니다`: 로그인 후 새 글쓰기 화면이 완전히 열렸는지 확인합니다.
- `본문의 사진 위치 표시가 올바르지 않습니다`: 중간 사진 번호가 빠졌는지 TXT의 `[PHOTO_N]` 표시를 확인합니다. 뒤쪽 번호만 빠진 경우에는 자동으로 이어서 배치됩니다.
- `파일 저장에 실패했습니다`: 출력 폴더 쓰기 권한과 디스크 여유 공간을 확인합니다.

Ollama나 OpenAI 호출이 실패해도 오류 메시지를 출력한 뒤 프로그램이
안전하게 종료되며, Python 예외 화면이 그대로 노출되지 않습니다.

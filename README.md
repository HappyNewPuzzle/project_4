# 개인용 네이버 블로그 작성 비서

사진과 간단한 리뷰 정보를 OpenAI API에 전달해 네이버 블로그용 초안을
만드는 Python 콘솔 프로그램입니다. 자동 로그인이나 자동 게시 기능은
포함하지 않습니다.

## 주요 기능

- 음식점 리뷰와 상품 리뷰 템플릿 분리
- 로컬 사진 여러 장을 Vision 입력으로 분석
- 제목 후보 5개, 본문, 태그 10개 생성
- 결과를 `outputs/generated_posts`에 UTF-8 텍스트 파일로 저장
- `.env`의 API Key와 `data/settings.json`의 개인 문체 설정 사용
- 입력, API 호출, 파일 저장 오류 처리

## 폴더 구조

```text
project4/
├── main.py                 # 콘솔 입력과 전체 실행 흐름
├── config.py               # 환경 변수와 settings.json 로드
├── openai_client.py        # 이미지 인코딩과 OpenAI API 호출
├── post_generator.py       # 입력 검증, 프롬프트 구성, 결과 저장
├── prompts/
│   ├── restaurant_review.txt
│   └── product_review.txt
├── outputs/
│   └── generated_posts/
├── data/
│   └── settings.json
├── .env.example
├── requirements.txt
└── README.md
```

## 준비 사항

- Python 3.10 이상
- OpenAI API Key
- PNG, JPG/JPEG, WEBP 또는 움직이지 않는 GIF 사진

API 사용에는 계정의 API 요금이 발생할 수 있습니다. 사진 수가 많을수록
입력 토큰과 비용도 늘어납니다.

## 설치 방법

PowerShell에서 프로젝트 폴더로 이동한 뒤 가상 환경을 만듭니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

환경 변수 예시 파일을 복사합니다.

```powershell
Copy-Item .env.example .env
```

생성된 `.env`를 열어 `OPENAI_API_KEY`에 실제 Key를 입력합니다.
`.env`는 `.gitignore`에 포함되어 있으므로 저장소에 커밋되지 않습니다.

```dotenv
OPENAI_API_KEY=sk-실제_API_Key
OPENAI_MODEL=gpt-5.4-mini
```

## 실행 방법

```powershell
python main.py
```

화면 안내에 따라 리뷰 종류, 이름, 링크, 메모, 별점과 사진 경로를
입력합니다. 사진 경로는 한 줄에 하나씩 입력하고, 모두 입력한 뒤 빈
줄에서 Enter를 누릅니다. Windows 탐색기의 **경로로 복사** 기능으로
가져온 따옴표 포함 경로도 사용할 수 있습니다.

생성이 끝나면 결과가 콘솔에 표시되고 다음 위치에 저장됩니다.

```text
outputs/generated_posts/YYYYMMDD_HHMMSS_이름.txt
```

## 블로그 스타일 바꾸기

`data/settings.json`의 문구를 원하는 말투로 수정하세요. JSON 문법상
각 항목 사이의 쉼표와 큰따옴표는 유지해야 합니다.

글의 전체 구조를 바꾸려면 `prompts/restaurant_review.txt` 또는
`prompts/product_review.txt`를 수정하면 됩니다.

## 오류 해결

- `OPENAI_API_KEY가 없습니다`: `.env` 파일과 Key 값을 확인합니다.
- `사진 파일을 찾을 수 없습니다`: 경로가 정확하고 파일이 존재하는지 확인합니다.
- `OpenAI API 호출에 실패했습니다`: 인터넷 연결, API Key, 사용 한도와 모델 접근 권한을 확인합니다.
- `파일 저장에 실패했습니다`: 출력 폴더 쓰기 권한과 디스크 여유 공간을 확인합니다.

실제 API 호출이 실패해도 오류 메시지를 출력한 뒤 프로그램이 안전하게
종료되며, Python 예외 화면이 그대로 노출되지 않습니다.

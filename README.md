# 📘 Gemini PDF 학습 도우미 (AI Study Assistant)
Gemini 2.5 Flash 모델을 활용하여 PDF 문서에서 학습 문제를 자동으로 생성하고, 에빙하우스의 망각 곡선 이론에 기반한 복습 시스템을 제공하는 Streamlit 웹 애플리케이션입니다.

✨ 주요 기능
📂 PDF 기반 문제 생성: PDF 파일을 업로드하면 AI가 텍스트와 이미지를 분석하여 핵심 문제를 생성합니다. (객관식, 단답형, 주관식)

🤖 멀티모달 AI (Gemini 2.5): 텍스트뿐만 아니라 PDF 내의 도표, 그림까지 분석하여 문제를 출제합니다.

🧠 나만의 복습 알고리즘: 맞힌 문제는 복습 주기를 늘리고, 틀린 문제는 초기화하는 SRS(Spaced Repetition System) 알고리즘을 적용했습니다.

✍️ 인터랙티브 학습: 정답을 바로 보여주지 않고, 사용자가 직접 답안을 입력해본 후 정답과 비교할 수 있습니다.

📊 학습 현황 대시보드: 전체 문제 수, 마스터(Lv.5)한 문제 수, 오늘 복습해야 할 문제 등을 한눈에 확인합니다.

🛠 기술 스택
Language: Python 3.9+

UI Framework: Streamlit

AI Model: Google Gemini 2.5 Flash (gemini-2.5-flash)

PDF Parsing: PyMuPDF (fitz)

Data Storage: JSON (Local File)

## 🚀 설치 및 실행 방법

### 1. 프로젝트 클론

git clone https://github.com/kth0727/python_review_program.git

### 2. 가상환경 생성 (권장)

Windows

python -m venv venv
source venv/Scripts/activate

Mac/Linux

python3 -m venv venv
source venv/bin/activate

## 3. 필수 라이브러리 설치

아래 라이브러리들을 설치합니다.

Bash

pip install streamlit pymupdf google-generativeai python-dotenv pillow

## 4. API 키 설정
프로젝트 폴더에 .env 파일을 생성하고, Google Gemini API 키를 입력하세요. (API 키 발급: Google AI Studio)

.env 파일 내용:

코드 스니펫

GEMINI_API_KEY=여기에_당신의_API_키를_붙여넣으세요

## 5. 애플리케이션 실행
터미널에서 아래 명령어를 입력하여 앱을 실행합니다.

Bash

streamlit run app.py

실행이 안 될 경우 python -m streamlit run app.py를 사용하세요.

## 📖 사용 가이드
1️⃣ 문제 생성 (Tab 1)
[문제 생성] 탭으로 이동합니다.

공부할 PDF 파일을 업로드합니다.

"🚀 문제 생성 시작" 버튼을 클릭합니다.

생성된 문제는 자동으로 review_db.json에 저장됩니다.

2️⃣ 오늘의 복습 (Tab 2)
[오늘의 복습] 탭으로 이동합니다.

"🔄 복습 목록 불러오기" 버튼을 누르면 오늘 복습해야 할 문제들이 로드됩니다.

문제를 읽고 입력창에 자신의 답을 적습니다.

**"👀 정답 확인"**을 눌러 실제 정답과 비교합니다.

채점 결과에 따라 버튼을 클릭합니다:

✅ 맞음: 레벨 상승 (다음 복습 간격이 길어짐)

❌ 틀림: 레벨 초기화 (내일 다시 복습)

3️⃣ 학습 통계 (Tab 3)
현재까지 저장된 문제 현황과 레벨 분포를 확인할 수 있습니다.

📂 폴더 구조
📂 Project Root

├── app.py              # 메인 애플리케이션 코드

├── review_db.json      # 생성된 문제와 복습 데이터가 저장되는 DB

├── .env                # API 키 설정 파일 (생성 필요)

├── requirements.txt    # 의존성 패키지 목록

└── README.md           # 설명서

❗ 트러블슈팅

Q. streamlit 명령어를 찾을 수 없다는 오류가 떠요.
A. 파이썬 환경 변수 문제일 수 있습니다. 아래 명령어로 실행해 보세요.

python -m streamlit run app.py
Q. 문제가 생성되지 않아요.
A. PDF가 암호화되어 있거나, 이미지/텍스트 추출이 불가능한 스캔본일 경우 인식이 어려울 수 있습니다. 또한 .env 파일에 API 키가 올바르게 들어갔는지 확인해 주세요.

License: MIT Created by: [권태환/kth0727]

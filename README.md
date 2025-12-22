# 📘 Gemini PDF 학습 도우미 (Python Review Program)

<br>

Google Gemini 2.5 Flash 모델을 활용하여 PDF 문서에서 학습 문제를 자동으로 생성하고, 에빙하우스의 망각 곡선 이론에 기반한 복습 시스템을 제공하는 Streamlit 웹 애플리케이션입니다.

특히 프로그래밍 코드나 도표/이미지가 포함된 전공 서적 학습에 최적화되어 있습니다.

<br>

✨ 주요 기능

<br>

📂 PDF 기반 멀티모달 문제 생성:

PDF 내의 텍스트뿐만 아니라 이미지, 도표, 코드 스크린샷을 AI가 분석하여 문제를 출제합니다.

<br>

🎯 두 가지 출제 모드:

📝 일반/암기 모드: 역사, 개념, 이론 등 암기가 필요한 내용.

💻 프로그래밍/코딩 모드: 코드의 실행 결과 예측, 버그 찾기, 문법 확인 등 코딩 테스트 스타일의 문제 생성.

<br>

🖼️ 스마트 이미지 연동:

PDF에서 이미지를 자동 추출하여 문제와 연결합니다.

질문 텍스트에 코드를 중복해서 적지 않고, **"위 이미지를 참고하세요"**라며 깔끔하게 이미지를 띄워줍니다.

<br>

🧠 나만의 복습 알고리즘 (SRS):

맞힌 문제는 복습 주기를 늘리고, 틀린 문제는 초기화하는 간격 반복 학습 시스템을 적용했습니다.

<br>

✍️ 인터랙티브 학습:

정답을 바로 보여주지 않고, 사용자가 직접 답안을 입력해본 후 정답과 비교할 수 있습니다.

<br>

🛠 기술 스택
Language: Python 3.9+

UI Framework: Streamlit

AI Model: Google Gemini 2.5 Flash

PDF Processing: PyMuPDF (fitz)

Image Processing: Pillow

<br><br>

# 🚀 설치 및 실행 방법

<br>

1. 프로젝트 클론

git clone https://github.com/kth0727/python_review_program.git

<br>

2. 필수 라이브러리 설치

가상환경(venv) 사용을 권장합니다.

cmd

pip install streamlit pymupdf google-generativeai python-dotenv pillow

<br>

3. API 키 설정
프로젝트 루트 경로에 .env 파일을 생성하고, Google Gemini API 키를 입력하세요. (API 키 발급: Google AI Studio)

.env 파일 내용:

코드 스니펫

GEMINI_API_KEY=여기에_당신의_API_키를_붙여넣으세요

<br>

4. 애플리케이션 실행

터미널에서 아래 명령어를 입력하여 앱을 실행합니다.

python -m streamlit run app.py

<br>

## 📖 사용 가이드

<br>

1️⃣ 문제 생성 (Tab 1)

<br>

학습 주제 선택:

일반/암기: 개념 위주의 문제.

프로그래밍/코딩: 코드 해석 및 로직 문제 (이미지 속 코드 분석 강화).

PDF 업로드: 공부할 파일을 올리고 **"🚀 문제 생성 시작"**을 클릭합니다.

추출된 이미지와 생성된 문제가 review.db 및 review_images/ 폴더에 저장됩니다.

<br>

2️⃣ 오늘의 복습 (Tab 2)

<br>

"🔄 복습 목록 불러오기" 버튼을 누릅니다.


문제를 확인합니다. (관련된 이미지가 있다면 질문 위에 표시됩니다.)


**"✍️ 정답 입력란"**에 답을 적고 **"👀 정답 확인"**을 누릅니다.


채점 결과에 따라 버튼을 클릭합니다:


✅ 맞음: 레벨 상승 (다음 복습 간격이 길어짐)


❌ 틀림: 레벨 초기화 (내일 다시 복습)

<br>

3️⃣ 학습 통계 (Tab 3)

전체 문제 수, 이미지 포함 문제 수, 마스터(Lv.5) 달성 현황 등을 그래프로 확인합니다.

<br>

📂 폴더 구조

python_review_program/

├── app.py              # 메인 애플리케이션 코드

├── review.db      # 문제 데이터베이스 (자동 생성)

├── review_images/      # PDF에서 추출된 이미지 저장소 (자동 생성)

├── .env                # API 키 설정 파일 (생성 필요)

└── README.md           # 설명서

<br>

❗ 트러블슈팅

Q. streamlit 명령어를 찾을 수 없다는 오류가 떠요.
A. 파이썬 환경 변수 문제일 수 있습니다. 아래 명령어로 실행해 보세요.


Q. 이미지가 너무 많이 저장돼요.
A. review_images 폴더에 이미지가 저장됩니다. 필요 없다면 해당 폴더의 파일들을 수동으로 삭제해도 되지만, 복습 시 이미지가 엑박으로 뜰 수 있습니다.

Created by: kth0727

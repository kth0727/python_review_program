import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
from PIL import Image
import io
import json
import os
from datetime import datetime, timedelta
import re
import random
from dotenv import load_dotenv

# ============================
# 설정 및 초기화
# ============================
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 페이지 설정 (반드시 가장 먼저 호출)
st.set_page_config(page_title="Gemini 학습 도우미", page_icon="📘", layout="wide")

if not GEMINI_API_KEY:
    st.error("❌ .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
GEMINI_MODEL_NAME = "gemini-2.5-flash"  # 최신 모델 권장
DB_PATH = "review_db.json"

# ============================
# 유틸리티 함수
# ============================
def load_review_db():
    if not os.path.exists(DB_PATH):
        return []
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_review_db(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def next_interval_days(level: int) -> int:
    mapping = {1: 1, 2: 2, 3: 4, 4: 7, 5: 15}
    return mapping.get(level, 1)

def extract_text_from_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    return text.strip()

def extract_images_from_pdf(file_bytes, max_images=3):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images = []
    for page in doc:
        img_list = page.get_images(full=True)
        for img_info in img_list:
            xref = img_info[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.n >= 5:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            images.append(img)
            pix = None
            if len(images) >= max_images:
                return images
    return images

def extract_json_from_text(raw: str) -> str:
    match = re.search(r'\[\s*\{(.|\s)*?\}\s*\]', raw)
    if match:
        return match.group(0)
    return ""

def generate_qa_with_gemini(text, images):
    model = genai.GenerativeModel(
        GEMINI_MODEL_NAME,
        generation_config={"response_mime_type": "application/json"}
    )
    
    prompt = """
    너는 교육용 문제를 만드는 AI이다. 
    제공된 텍스트와 이미지를 기반으로 학습용 문제 5개를 생성하라.
    JSON 배열 형식으로만 응답하라.

    필수 규칙:
    1. 문제는 총 5개 생성 (최소 2개는 이미지 관련 문제).
    2. JSON 포맷:
       [
         {"type": "multiple_choice", "question": "...", "choices": ["A", "B", "C", "D"], "answer": "정답"},
         {"type": "short_answer", "question": "...", "answer": "정답"},
         {"type": "subjective", "question": "...", "answer": "정답"}
       ]
    3. 객관식(multiple_choice)은 반드시 "choices" 항목(4개 보기)이 있어야 함.
    """
    
    parts = [prompt] + images + [f"텍스트 내용:\n{text}"]
    response = model.generate_content(parts)
    return response.text

def parse_qa_json(raw_text):
    text_to_parse = raw_text.strip()
    try:
        data = json.loads(text_to_parse)
    except json.JSONDecodeError:
        extracted = extract_json_from_text(text_to_parse)
        if not extracted:
            return []
        try:
            data = json.loads(extracted)
        except:
            return []
            
    result = []
    for item in data:
        if "question" in item and "answer" in item:
            # 객관식인데 보기가 없으면 제외
            if item.get("type") == "multiple_choice" and len(item.get("choices", [])) < 4:
                continue
            result.append(item)
    return result

# ============================
# 세션 상태 초기화
# ============================
if "review_session" not in st.session_state:
    st.session_state.review_session = []
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "show_answer" not in st.session_state:
    st.session_state.show_answer = False

# ============================
# 메인 UI
# ============================

st.title("📘 Gemini PDF 학습 도우미")
st.markdown("PDF를 업로드하여 AI 문제를 생성하고, 망각 곡선 이론에 따라 복습하세요.")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📂 문제 생성", "📝 오늘의 복습", "📊 학습 통계"])

# --- TAB 1: 문제 생성 ---
with tab1:
    st.header("PDF에서 문제 추출")
    uploaded_file = st.file_uploader("PDF 파일을 드래그하거나 선택하세요", type=["pdf"])

    if uploaded_file is not None:
        if st.button("🚀 문제 생성 시작", type="primary"):
            with st.spinner("PDF 분석 및 Gemini가 문제를 생성 중입니다... (약 10~20초 소요)"):
                try:
                    file_bytes = uploaded_file.read()
                    text = extract_text_from_pdf(file_bytes)
                    images = extract_images_from_pdf(file_bytes)

                    if not text and not images:
                        st.error("PDF에서 텍스트나 이미지를 추출할 수 없습니다.")
                    else:
                        raw_json = generate_qa_with_gemini(text, images)
                        qa_list = parse_qa_json(raw_json)

                        if qa_list:
                            db = load_review_db()
                            today = datetime.today().date().isoformat()
                            # ID 부여 로직
                            next_id = max([item.get("id", 0) for item in db], default=0) + 1
                            
                            for qa in qa_list:
                                qa["id"] = next_id
                                qa["level"] = 1
                                qa["next_review_date"] = today
                                db.append(qa)
                                next_id += 1
                            
                            save_review_db(db)
                            st.success(f"✅ 총 {len(qa_list)}개의 문제가 생성되어 저장되었습니다!")
                            
                            # 미리보기
                            with st.expander("생성된 문제 미리보기"):
                                st.json(qa_list)
                        else:
                            st.error("Gemini 응답을 처리하는 데 실패했습니다. 다시 시도해주세요.")
                            st.code(raw_json) # 디버깅용
                except Exception as e:
                    st.error(f"오류 발생: {e}")

# --- TAB 2: 오늘의 복습 ---
with tab2:
    st.header("오늘의 복습")
    
    # 복습 세션 로드 버튼 (혹은 자동 로드)
    if st.button("🔄 복습 목록 불러오기"):
        db = load_review_db()
        today = datetime.today().date().isoformat()
        # 오늘 날짜 이하인 것들 필터링
        due_items = [item for item in db if item.get("next_review_date", "9999-12-31") <= today]
        
        if not due_items:
            st.info("🎉 오늘 복습할 문제가 없습니다! 푹 쉬세요.")
            st.session_state.review_session = []
        else:
            # 랜덤 섞기 및 레벨 정렬
            due_items.sort(key=lambda x: (x["next_review_date"], -x.get("level", 1)))
            random.shuffle(due_items)
            st.session_state.review_session = due_items
            st.session_state.current_index = 0
            st.session_state.show_answer = False
            st.rerun()

    # 문제 표시 로직
    if st.session_state.review_session:
        idx = st.session_state.current_index
        total = len(st.session_state.review_session)
        
        if idx < total:
            item = st.session_state.review_session[idx]
            q_type = item.get("type", "Etc")
            
            # 진행률 바
            st.progress((idx) / total, text=f"진행 상황: {idx + 1} / {total}")
            
            # 카드 스타일 컨테이너
            with st.container(border=True):
                st.caption(f"ID: {item.get('id')} | Level: {item.get('level')} | Type: {q_type}")
                st.subheader(f"Q. {item.get('question')}")
                
                if q_type == "multiple_choice":
                    st.markdown("**보기:**")
                    for i, choice in enumerate(item.get("choices", [])):
                        st.markdown(f"{i+1}. {choice}")

            # 정답 확인 영역
            if not st.session_state.show_answer:
                if st.button("👀 정답 보기", use_container_width=True):
                    st.session_state.show_answer = True
                    st.rerun()
            else:
                st.info(f"**정답:** {item.get('answer')}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 맞음 (레벨 UP)", use_container_width=True, type="primary"):
                        # DB 업데이트
                        full_db = load_review_db()
                        for q in full_db:
                            if q["id"] == item["id"]:
                                q["level"] = min(q.get("level", 1) + 1, 5)
                                interval = next_interval_days(q["level"])
                                q["next_review_date"] = (datetime.today().date() + timedelta(days=interval)).isoformat()
                                break
                        save_review_db(full_db)
                        
                        # 다음 문제로
                        st.session_state.current_index += 1
                        st.session_state.show_answer = False
                        st.rerun()
                        
                with col2:
                    if st.button("❌ 틀림 (레벨 초기화)", use_container_width=True):
                        # DB 업데이트
                        full_db = load_review_db()
                        for q in full_db:
                            if q["id"] == item["id"]:
                                q["level"] = 1
                                interval = 1
                                q["next_review_date"] = (datetime.today().date() + timedelta(days=interval)).isoformat()
                                break
                        save_review_db(full_db)
                        
                        # 다음 문제로
                        st.session_state.current_index += 1
                        st.session_state.show_answer = False
                        st.rerun()

        else:
            st.balloons()
            st.success("🎉 오늘 복습을 모두 완료했습니다!")
            if st.button("처음으로"):
                st.session_state.review_session = []
                st.rerun()
    else:
        st.write("👆 위 버튼을 눌러 복습을 시작하세요.")

# --- TAB 3: 통계 (간단 버전) ---
with tab3:
    st.header("📊 학습 데이터베이스 통계")
    db = load_review_db()
    if db:
        total_q = len(db)
        levels = [item.get("level", 1) for item in db]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("총 문제 수", f"{total_q}개")
        col2.metric("마스터(Lv.5) 도달", f"{levels.count(5)}개")
        col3.metric("오늘 복습 대상", f"{len([i for i in db if i.get('next_review_date') <= datetime.today().date().isoformat()])}개")
        
        st.markdown("#### 레벨 분포")
        level_counts = {i: levels.count(i) for i in range(1, 6)}
        st.bar_chart(level_counts)
        
        with st.expander("전체 데이터 보기"):
            st.dataframe(db)
    else:
        st.warning("저장된 데이터가 없습니다.")
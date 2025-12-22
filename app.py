import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
from PIL import Image
import io
import json
import os
import uuid
import sqlite3
from datetime import datetime, timedelta
import re
import random
from dotenv import load_dotenv

# ============================
# 설정 및 초기화
# ============================
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

st.set_page_config(page_title="Gemini 학습 도우미", page_icon="📘", layout="wide")

if not GEMINI_API_KEY:
    st.error("❌ .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
GEMINI_MODEL_NAME = "gemini-2.5-flash"

DB_NAME = "review.db"
IMG_DIR = "review_images"

if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

# ============================
# SQLite DB 함수
# ============================
def init_db():
    """DB 테이블이 없으면 생성"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT,
            type TEXT,
            question TEXT,
            choices TEXT,
            answer TEXT,
            explanation TEXT,
            related_image_path TEXT,
            level INTEGER,
            next_review_date TEXT,
            category TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_questions_to_db(qa_list, source_file, category):
    """생성된 문제 리스트를 DB에 삽입"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    today = datetime.today().date().isoformat()
    created_at = datetime.now().isoformat()
    
    for qa in qa_list:
        choices_str = json.dumps(qa.get("choices", []), ensure_ascii=False)
        
        c.execute('''
            INSERT INTO questions 
            (source_file, type, question, choices, answer, explanation, related_image_path, level, next_review_date, category, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            source_file,
            qa.get("type"),
            qa.get("question"),
            choices_str,
            qa.get("answer"),
            qa.get("explanation", "해설이 없습니다."),
            qa.get("related_image_path"),
            1,
            today,
            category,
            created_at
        ))
    conn.commit()
    conn.close()

def get_due_questions(target_date):
    """복습 날짜가 된 문제들을 가져오기 (필터링 제거됨)"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # ✅ [수정됨] 파일 조건 없이 날짜로만 조회
    query = "SELECT * FROM questions WHERE next_review_date <= ?"
    c.execute(query, (target_date,))
    rows = c.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        item = dict(row)
        item["choices"] = json.loads(item["choices"]) if item["choices"] else []
        result.append(item)
    return result

def update_question_level(q_id, new_level, next_date):
    """문제의 레벨과 다음 복습일 업데이트"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        UPDATE questions 
        SET level = ?, next_review_date = ?
        WHERE id = ?
    ''', (new_level, next_date, q_id))
    conn.commit()
    conn.close()

def get_stats():
    """통계용 데이터 조회"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) as cnt FROM questions")
    total_q = c.fetchone()['cnt']
    
    c.execute("SELECT level, COUNT(*) as cnt FROM questions GROUP BY level")
    levels = {row['level']: row['cnt'] for row in c.fetchall()}
    
    conn.close()
    return total_q, levels

# 앱 시작 시 DB 초기화
init_db()

# ============================
# 유틸리티 함수
# ============================
def next_interval_days(level: int) -> int:
    mapping = {1: 1, 2: 2, 3: 4, 4: 7, 5: 15}
    return mapping.get(level, 1)

def extract_text_from_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    return text.strip()

def extract_images_from_pdf(file_bytes, max_images=5):
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

def save_image_local(pil_image):
    unique_filename = f"{uuid.uuid4().hex}.png"
    file_path = os.path.join(IMG_DIR, unique_filename)
    pil_image.save(file_path)
    return file_path

def extract_json_from_text(raw: str) -> str:
    match = re.search(r'\[\s*\{(.|\s)*?\}\s*\]', raw)
    if match:
        return match.group(0)
    return ""

def generate_qa_with_gemini(text, images, mode="general"):
    model = genai.GenerativeModel(
        GEMINI_MODEL_NAME,
        generation_config={"response_mime_type": "application/json"}
    )
    
    img_count = len(images)
    
    common_format = f"""
    필수 규칙:
    1. 문제는 총 5개 생성.
    2. JSON 데이터에 반드시 **"explanation"** 필드를 추가하여 정답에 대한 상세한 해설을 적어라.
    3. 특정 문제에 이미지가 사용되었다면, 'image_index' 필드에 해당 이미지의 순서(0부터 시작하는 숫자)를 포함하라.
    4. 현재 제공된 이미지는 총 {img_count}개이다. (인덱스는 0 ~ {img_count - 1})

    JSON 포맷 예시:
       [
         {{
            "type": "multiple_choice", 
            "question": "...", 
            "choices": ["A", "B", "C", "D"], 
            "answer": "...", 
            "explanation": "이것이 정답인 이유는...", 
            "image_index": 0
         }},
         {{
            "type": "short_answer", 
            "question": "...", 
            "answer": "...", 
            "explanation": "해당 용어의 정의는...",
            "image_index": null
         }}
       ]
    """

    if mode == "coding":
        prompt = f"""
        너는 '컴퓨터 공학 및 프로그래밍 튜터'이다.
        제공된 텍스트와 이미지를 기반으로 **프로그래밍/코딩 능력**을 테스트하는 문제 5개를 생성하라.
        JSON 배열 형식으로만 응답하라.

        [문제 출제 가이드]
        1. 단순 암기보다는 **코드의 실행 결과 예측**, **버그 찾기**, **올바른 문법 고르기** 등의 문제를 우선적으로 출제하라.
        2. "explanation" 필드에는 코드가 왜 그렇게 동작하는지 논리적으로 설명하라.
        3. **중요: 이미지를 활용하는 문제의 경우, 이미지 속에 있는 코드를 질문 텍스트에 다시 적지 마라.**
           - 좋은 예: "Q. 위 이미지(Program 8.1)의 코드를 실행했을 때 반환되는 값은 무엇입니까?"
        4. 이미지가 없는 문제일 경우에만 마크다운 코드 블록(```)을 사용하여 코드 예시를 포함하라.
        
        {common_format}
        """
    else:
        prompt = f"""
        너는 교육용 문제를 만드는 AI이다. 
        제공된 텍스트와 이미지를 기반으로 학습용 문제 5개를 생성하라.
        JSON 배열 형식으로만 응답하라.

        [문제 출제 가이드]
        1. 텍스트의 핵심 내용과 이미지(도표, 그림)를 분석하여 골고루 출제하라.
        2. "explanation" 필드에는 해당 개념의 배경이나 이유를 설명하라.
        3. 이미지를 사용할 때는 "위 그림을 참고하여..."와 같이 질문하라.
        
        {common_format}
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
st.markdown("PDF를 업로드하면 AI가 텍스트와 **사진**을 분석하여 문제를 만듭니다.")

tab1, tab2, tab3 = st.tabs(["📂 문제 생성", "📝 오늘의 복습", "📊 학습 통계"])

# --- TAB 1: 문제 생성 ---
with tab1:
    st.header("PDF에서 문제 추출")
    
    st.markdown("### 1. 학습 주제 선택")
    subject_mode = st.radio(
        "어떤 유형의 문제를 생성할까요?",
        ("📝 일반/암기 (개념, 역사, 이론 등)", "💻 프로그래밍/코딩 (코드 해석, 문법, 로직)"),
        index=0,
        horizontal=True
    )
    mode_key = "coding" if "프로그래밍" in subject_mode else "general"

    st.markdown("### 2. 파일 업로드")
    uploaded_file = st.file_uploader("PDF 파일을 드래그하거나 선택하세요", type=["pdf"])

    if uploaded_file is not None:
        if st.button("🚀 문제 생성 시작", type="primary"):
            with st.spinner(f"{GEMINI_MODEL_NAME} 모델이 이미지를 분석하고 문제를 생성 중입니다..."):
                try:
                    file_bytes = uploaded_file.read()
                    text = extract_text_from_pdf(file_bytes)
                    extracted_pil_images = extract_images_from_pdf(file_bytes)
                    
                    saved_image_paths = []
                    for img in extracted_pil_images:
                        path = save_image_local(img)
                        saved_image_paths.append(path)

                    if not text and not extracted_pil_images:
                        st.error("PDF에서 텍스트나 이미지를 추출할 수 없습니다.")
                    else:
                        raw_json = generate_qa_with_gemini(text, extracted_pil_images, mode=mode_key)
                        qa_list = parse_qa_json(raw_json)

                        if qa_list:
                            count_img_qs = 0
                            for qa in qa_list:
                                img_idx = qa.get("image_index")
                                if img_idx is not None and isinstance(img_idx, int):
                                    if 0 <= img_idx < len(saved_image_paths):
                                        qa["related_image_path"] = saved_image_paths[img_idx]
                                        count_img_qs += 1
                                else:
                                    qa["related_image_path"] = None

                            add_questions_to_db(qa_list, uploaded_file.name, mode_key)
                            
                            st.success(f"✅ 총 {len(qa_list)}개의 문제가 생성되었습니다! (이미지 활용 문제: {count_img_qs}개)")
                            
                            if saved_image_paths:
                                st.markdown("##### 📸 PDF에서 발견된 이미지들")
                                cols = st.columns(len(saved_image_paths))
                                for i, img_path in enumerate(saved_image_paths):
                                    with cols[i % 5]:
                                        # ✅ [수정됨] 썸네일은 작게 표시
                                        st.image(img_path, caption=f"Index {i}", width=150)
                            
                            with st.expander("생성된 문제 데이터 확인"):
                                st.json(qa_list)
                        else:
                            st.error("Gemini 응답을 처리하는 데 실패했습니다.")
                            st.code(raw_json)
                except Exception as e:
                    st.error(f"오류 발생: {e}")

# --- TAB 2: 오늘의 복습 ---
with tab2:
    st.header("오늘의 복습")
    
    # ✅ [수정됨] 3번 기능(필터) 삭제 -> 단순 버튼만 남김
    if st.button("🔄 복습 목록 불러오기", use_container_width=True):
        today = datetime.today().date().isoformat()
        
        due_items = get_due_questions(today)
        
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

    if st.session_state.review_session:
        idx = st.session_state.current_index
        total = len(st.session_state.review_session)
        
        if idx < total:
            item = st.session_state.review_session[idx]
            q_type = item.get("type", "Etc")
            
            st.progress((idx) / total, text=f"진행 상황: {idx + 1} / {total}")
            
            with st.container(border=True):
                category_tag = item.get("category", "General").upper()
                st.caption(f"ID: {item.get('id')} | Level: {item.get('level')} | [{category_tag}]")
                
                # ✅ [수정됨] 이미지 크기 고정 (width=500)
                if item.get("related_image_path") and os.path.exists(item.get("related_image_path")):
                    st.image(item["related_image_path"], caption="참고 이미지", width=500)
                
                st.subheader(f"Q. {item.get('question')}")
                
                if "```" in item.get('question') and not item.get("related_image_path"):
                     st.info("💡 코드 블록을 확인하고 답하세요.")

                if q_type == "multiple_choice":
                    st.markdown("**보기:**")
                    for i, choice in enumerate(item.get("choices", [])):
                        st.markdown(f"{i+1}. {choice}")

                user_input = st.text_area(
                    "✍️ 여기에 정답을 적어보세요:",
                    height=100,
                    key=f"user_input_{item['id']}",
                    disabled=st.session_state.show_answer
                )

            if not st.session_state.show_answer:
                if st.button("👀 정답 확인", use_container_width=True):
                    st.session_state.show_answer = True
                    st.rerun()
            else:
                st.divider()
                col_u, col_a = st.columns(2)
                with col_u:
                    st.markdown("**📝 내가 쓴 답:**")
                    my_ans = st.session_state.get(f"user_input_{item['id']}", "(입력 없음)")
                    if my_ans.strip() == "":
                        st.warning("(입력 내용이 없습니다)")
                    else:
                        st.info(my_ans)
                
                with col_a:
                    st.markdown("**💡 실제 정답:**")
                    st.success(item.get('answer'))
                
                # 해설(Explanation) 표시
                if item.get("explanation"):
                    st.markdown("### 🎓 해설")
                    st.info(item.get("explanation"))

                st.write("---")
                st.markdown("##### 채점하기")
                
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("✅ 맞음 (레벨 UP)", use_container_width=True, type="primary"):
                        new_level = min(item.get("level", 1) + 1, 5)
                        interval = next_interval_days(new_level)
                        next_date = (datetime.today().date() + timedelta(days=interval)).isoformat()
                        
                        update_question_level(item["id"], new_level, next_date)
                        
                        st.session_state.current_index += 1
                        st.session_state.show_answer = False
                        st.rerun()
                        
                with btn_col2:
                    if st.button("❌ 틀림 (레벨 초기화)", use_container_width=True):
                        new_level = 1
                        interval = 1
                        next_date = (datetime.today().date() + timedelta(days=interval)).isoformat()
                        
                        update_question_level(item["id"], new_level, next_date)
                        
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

# --- TAB 3: 통계 ---
with tab3:
    st.header("📊 학습 데이터베이스 통계")
    
    total_q, levels = get_stats()
    
    if total_q > 0:
        col1, col2 = st.columns(2)
        col1.metric("총 문제 수", f"{total_q}개")
        col2.metric("마스터(Lv.5) 도달", f"{levels.get(5, 0)}개")
        
        st.markdown("---")
        st.markdown("#### 레벨별 분포")
        level_chart_data = {i: levels.get(i, 0) for i in range(1, 6)}
        st.bar_chart(level_chart_data)
    else:
        st.warning("아직 저장된 문제가 없습니다.")
import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
from PIL import Image
import io
import json
import os
import uuid
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
DB_PATH = "review_db.json"
IMG_DIR = "review_images"

if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

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

# ✅ [수정됨] 프롬프트 수정: 이미지가 있으면 텍스트 중복 방지
def generate_qa_with_gemini(text, images, mode="general"):
    model = genai.GenerativeModel(
        GEMINI_MODEL_NAME,
        generation_config={"response_mime_type": "application/json"}
    )
    
    img_count = len(images)
    
    common_format = f"""
    필수 규칙:
    1. 문제는 총 5개 생성.
    2. 특정 문제에 이미지가 사용되었다면, 'image_index' 필드에 해당 이미지의 순서(0부터 시작하는 숫자)를 반드시 포함하라.
    3. 이미지가 필요 없는 문제는 'image_index' 필드를 생략하거나 null로 두라.
    4. 현재 제공된 이미지는 총 {img_count}개이다. (인덱스는 0 ~ {img_count - 1})

    JSON 포맷 예시:
       [
         {{"type": "multiple_choice", "question": "...", "choices": ["A", "B", "C", "D"], "answer": "...", "image_index": 0}},
         {{"type": "short_answer", "question": "...", "answer": "...", "image_index": null}}
       ]
    """

    if mode == "coding":
        # 💻 코딩 모드 프롬프트 (강력하게 수정됨)
        prompt = f"""
        너는 '컴퓨터 공학 및 프로그래밍 튜터'이다.
        제공된 텍스트와 이미지를 기반으로 **프로그래밍/코딩 능력**을 테스트하는 문제 5개를 생성하라.
        JSON 배열 형식으로만 응답하라.

        [문제 출제 가이드]
        1. 단순 암기보다는 **코드의 실행 결과 예측**, **버그 찾기**, **올바른 문법 고르기** 등의 문제를 우선적으로 출제하라.
        
        2. **중요: 이미지를 활용하는 문제의 경우, 이미지 속에 있는 코드를 질문 텍스트에 다시 적지 마라.**
           - 나쁜 예: "Q. ```c int main() {{ ... }} ``` 위 코드는 무엇을 출력합니까?"
           - 좋은 예: "Q. 위 이미지(Program 8.1)의 코드를 실행했을 때 반환되는 값은 무엇입니까?"
        
        3. 이미지가 없는 문제일 경우에만 마크다운 코드 블록(```)을 사용하여 코드 예시를 포함하라.
        
        {common_format}
        """
    else:
        prompt = f"""
        너는 교육용 문제를 만드는 AI이다. 
        제공된 텍스트와 이미지를 기반으로 학습용 문제 5개를 생성하라.
        JSON 배열 형식으로만 응답하라.

        [문제 출제 가이드]
        1. 텍스트의 핵심 내용과 이미지(도표, 그림)를 분석하여 골고루 출제하라.
        2. 이미지가 있다면 최소 2문제는 이미지 관련 문제로 출제하라.
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
                            db = load_review_db()
                            today = datetime.today().date().isoformat()
                            next_id = max([item.get("id", 0) for item in db], default=0) + 1
                            
                            count_img_qs = 0
                            for qa in qa_list:
                                qa["id"] = next_id
                                qa["level"] = 1
                                qa["next_review_date"] = today
                                qa["category"] = mode_key
                                
                                img_idx = qa.get("image_index")
                                if img_idx is not None and isinstance(img_idx, int):
                                    if 0 <= img_idx < len(saved_image_paths):
                                        qa["related_image_path"] = saved_image_paths[img_idx]
                                        count_img_qs += 1
                                
                                db.append(qa)
                                next_id += 1
                            
                            save_review_db(db)
                            st.success(f"✅ 총 {len(qa_list)}개의 문제가 생성되었습니다! (이미지 활용 문제: {count_img_qs}개)")
                            
                            if saved_image_paths:
                                st.markdown("##### 📸 PDF에서 발견된 이미지들")
                                cols = st.columns(len(saved_image_paths))
                                for i, img_path in enumerate(saved_image_paths):
                                    with cols[i % 5]:
                                        st.image(img_path, caption=f"Index {i}", use_container_width=True)
                            
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
    
    if st.button("🔄 복습 목록 불러오기"):
        db = load_review_db()
        today = datetime.today().date().isoformat()
        due_items = [item for item in db if item.get("next_review_date", "9999-12-31") <= today]
        
        if not due_items:
            st.info("🎉 오늘 복습할 문제가 없습니다! 푹 쉬세요.")
            st.session_state.review_session = []
        else:
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
                
                # 이미지 출력
                if item.get("related_image_path") and os.path.exists(item.get("related_image_path")):
                    st.image(item["related_image_path"], caption="참고 이미지", use_container_width=True)
                
                st.subheader(f"Q. {item.get('question')}")
                
                # 코드 블록 경고는 유지하되, 이미지가 없을 때만 의미가 있음
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

                st.write("---")
                st.markdown("##### 채점하기")
                
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("✅ 맞음 (레벨 UP)", use_container_width=True, type="primary"):
                        full_db = load_review_db()
                        for q in full_db:
                            if q["id"] == item["id"]:
                                q["level"] = min(q.get("level", 1) + 1, 5)
                                interval = next_interval_days(q["level"])
                                q["next_review_date"] = (datetime.today().date() + timedelta(days=interval)).isoformat()
                                break
                        save_review_db(full_db)
                        
                        st.session_state.current_index += 1
                        st.session_state.show_answer = False
                        st.rerun()
                        
                with btn_col2:
                    if st.button("❌ 틀림 (레벨 초기화)", use_container_width=True):
                        full_db = load_review_db()
                        for q in full_db:
                            if q["id"] == item["id"]:
                                q["level"] = 1
                                interval = 1
                                q["next_review_date"] = (datetime.today().date() + timedelta(days=interval)).isoformat()
                                break
                        save_review_db(full_db)
                        
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
    db = load_review_db()
    if db:
        total_q = len(db)
        levels = [item.get("level", 1) for item in db]
        img_q_count = len([i for i in db if i.get("related_image_path")])
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 문제 수", f"{total_q}개")
        col2.metric("이미지 문제", f"{img_q_count}개")
        col3.metric("마스터(Lv.5)", f"{levels.count(5)}개")
        col4.metric("오늘 복습", f"{len([i for i in db if i.get('next_review_date') <= datetime.today().date().isoformat()])}개")
        
        st.markdown("#### 레벨 분포")
        level_counts = {i: levels.count(i) for i in range(1, 6)}
        st.bar_chart(level_counts)
        
        with st.expander("전체 데이터 보기"):
            st.dataframe(db)
    else:
        st.warning("저장된 데이터가 없습니다.")
import streamlit as st
import json
import requests
import os
from datetime import date

# --- 페이지 기본 세팅 ---
st.set_page_config(page_title="Clush AI Work Assistant", layout="wide")

st.title("Clush AI Work Assistant")
st.info("회의록이나 업무 지시사항을 입력하면, 시스템이 즉시 핵심 내용 요약과 다음 할 일을 구조화하여 추천해 줍니다.", icon=None)
st.divider()

# --- 샘플 데이터 로더 ---
DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "sample_data.json"))
try:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        sample_scenarios = json.load(f)
except Exception as e:
    st.error(f"샘플 데이터를 불러오는 중 오류 발생: {str(e)}")
    sample_scenarios = []

# --- 사이드바: 시나리오 선택기 ---
st.sidebar.header("데모 시나리오 로더")
st.sidebar.markdown("실제 업무 상황과 유사한 텍스트 샘플을 불러와 데모를 테스트할 수 있습니다.")
scenario_titles = ["선택 안 함 (직접 입력)"] + [s["scenario"] for s in sample_scenarios]
selected_scenario_title = st.sidebar.selectbox("테스트할 시나리오를 선택하세요:", scenario_titles)

default_text = ""
if selected_scenario_title != "선택 안 함 (직접 입력)":
    for s in sample_scenarios:
        if s["scenario"] == selected_scenario_title:
            default_text = s["raw_text"]
            break

# --- 입력 영역 ---
st.subheader("업무 내용 및 기본 정보 설정")
meeting_date = st.date_input(
    label="회의 일자 (작성일)",
    value=date.today(),
    help="기준일을 설정하면 '내일', '이번 주' 등 상대적 시간을 실제 캘린더 날짜로 변환해 줍니다."
)
user_input = st.text_area(
    label="분석할 회의록이나 텍스트를 입력하세요 (또는 좌측 메뉴에서 샘플 시나리오를 불러오세요):",
    value=default_text,
    height=200
)

# --- ICS 파일 생성 함수 ---
def generate_ics(tasks):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Clush AI Assistant//EN",
        "CALSCALE:GREGORIAN",
    ]
    for task in tasks:
        iso_str = task.get("마감기한_iso", "")
        if iso_str and str(iso_str).strip() not in ["미정", "None", ""]:
            dt = str(iso_str).replace("-", "").replace(":", "").replace(" ", "")
            if "T" not in dt:
                dt += "T090000"
            if "Z" not in dt:
                dt += "Z"
            lines.append("BEGIN:VEVENT")
            lines.append(f"DTSTART:{dt}")
            lines.append(f"DTEND:{dt}")
            lines.append(f"SUMMARY:[업무] {task.get('업무', '무제')} ({task.get('담당자', '미정')})")
            lines.append(f"DESCRIPTION:우선순위: {task.get('우선순위', '미정')} / 담당자: {task.get('담당자', '미정')}")
            lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)

# --- 분석 시작 버튼 ---
if st.button("분석 시작", type="primary"):
    if not user_input.strip():
        st.warning("경고: 텍스트를 1자 이상 먼저 입력해 주세요.")
    else:
        with st.spinner("자연어 모델이 텍스트를 분석하여 Task를 추출하고 있습니다..."):
            try:
                api_url = "http://localhost:8000/analyze"
                payload = {"text": user_input, "date": str(meeting_date)}
                response = requests.post(api_url, json=payload, timeout=30)

                if response.status_code == 200:
                    result = response.json()
                    tasks = result.get("tasks", [])
                    share_draft = result.get("share_draft", "")

                    st.success("문서 분석이 성공적으로 완료되었습니다.")
                    st.divider()

                    # ── 1. 핵심 요약 ──────────────────────────────────
                    st.subheader("핵심 요약")
                    st.info(result.get("summary", "요약 정보가 반환되지 않았습니다."), icon=None)

                    # ── 2. 다음 할 일 (표) ────────────────────────────
                    st.subheader("다음 할 일")
                    if tasks:
                        display_tasks = []
                        for t in tasks:
                            display_task = t.copy()
                            display_task.pop("마감기한_iso", None)
                            display_tasks.append(display_task)
                        st.table(display_tasks)
                    else:
                        st.write("도출된 할 일이 없습니다.")

                    # ── 3. 액션 대시보드: 좌(캘린더) | 우(공유) ────────
                    st.divider()
                    st.subheader("추가 작업")
                    col_left, col_right = st.columns(2)

                    # 좌측 박스: 캘린더 연동
                    with col_left:
                        with st.container(border=True):
                            st.markdown("#### 캘린더에 일정 추가")
                            st.markdown(
                                "분석된 모든 할 일의 마감 기한을 달력 파일(.ics)로 내보냅니다.  \n"
                                "구글 캘린더 또는 아웃룩에서 파일을 열면 일정이 자동 등록됩니다."
                            )
                            ics_data = generate_ics(tasks)
                            st.download_button(
                                label="캘린더에 일정 추가하기 (.ics 다운로드)",
                                data=ics_data,
                                file_name="clush_work_tasks.ics",
                                mime="text/calendar",
                                type="primary",
                                use_container_width=True
                            )

                    # 우측 박스: 사내 메신저 공유
                    with col_right:
                        with st.container(border=True):
                            st.markdown("#### 사내 메신저 공유")
                            st.markdown(
                                "아래 공유용 텍스트를 복사하여 슬랙(Slack), 잔디, 이메일 등에 바로 붙여넣기 하세요."
                            )
                            st.code(share_draft or "공유 문서 초안이 반환되지 않았습니다.", language=None)

                else:
                    st.error(f"백엔드 서버 오류 (상태 코드: {response.status_code})\n상세 내용: {response.text}")

            except requests.exceptions.ConnectionError:
                st.error("치명적 에러: 백엔드(FastAPI) 서버와 통신할 수 없습니다.")
                st.markdown("**해결 방법:** 터미널에서 `uvicorn backend.main:app --reload` 를 실행해 백엔드를 켜주세요.")
            except Exception as e:
                st.error(f"알 수 없는 장애 발생: {str(e)}")
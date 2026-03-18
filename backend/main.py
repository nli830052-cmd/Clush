import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv
import google.generativeai as genai

# 1️⃣ 환경변수 로드
load_dotenv()

# 2️⃣ Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY and GEMINI_API_KEY != "여기에_본인의_구글_API_키를_넣으세요":
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("⚠️ WARNING: 올바른 GEMINI_API_KEY가 .env 파일에 설정되지 않았습니다.")

# 3️⃣ FastAPI 앱 초기화
app = FastAPI(
    title="AI Work Assistant API",
    description="업무 내용을 분석하여 요약, 할 일, 우선순위를 추출하는 Clush WorkPlace 연동형 백엔드 API",
    version="1.0.0"
)

# 4️⃣ CORS 미들웨어 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실무에서는 ["http://localhost:8501"] 등으로 제한하지만 데모의 편의를 위해 완전 개방
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- 5️⃣ Pydantic 스키마 정의 -----------------
class WorkRequest(BaseModel):
    text: str = Field(..., description="분석할 원본 업무 텍스트 (회의록 등)")
    date: str = Field(..., description="회의 진행 일자 (YYYY-MM-DD 형식)")

class TaskItem(BaseModel):
    업무: str = Field(..., description="할 일 요약")
    담당자: str = Field(..., description="할 일 담당자 (파악 불가 시 '미정')")
    마감기한: str = Field(..., description="사용자가 읽기 편한 구체적 한국어 마감 기한 문자열")
    마감기한_iso: str = Field(..., description="분석한 마감기한 기반으로 구글 캘린더 일정 관리를 위한 ISO-8601 포맷(예: 2026-03-19T10:00:00). 시각을 모른다면 시간은 T09:00:00 처리. 정보가 아예 없으면 '미정'")
    우선순위: str = Field(..., description="중요도 (높음/중간/낮음)")

class WorkResponse(BaseModel):
    summary: str = Field(..., description="전체 회의록의 1-2줄 핵심 요약")
    share_draft: str = Field(..., description="팀 메신저(슬랙 등)나 이메일 공유(복사/붙여넣기) 목적의 부드러운 화법으로 작성된 전체 요령 요약 멘트")
    tasks: List[TaskItem] = Field(..., description="도출된 실행 가능한 할 일 목록")

# ----------------- 6️⃣ 비동기 API 엔드포인트 -----------------
@app.post("/analyze", response_model=WorkResponse, summary="업무 내용 분석 및 Action Item 추출")
async def analyze_work(req: WorkRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="분석할 텍스트가 비어있습니다. 데이터를 입력해주세요.")

    # 🎯 프롬프트 엔지니어링: 철저한 JSON 구조적 출력(Structured Output) 강제 및 날짜 컨텍스트 주입
    system_prompt = f"""
당신은 Clush WorkPlace의 최고 등급 AI 비서입니다. 
이 회의(텍스트)가 진행된 날짜는 기준일 [{req.date}] 입니다. 
반드시 이 기준일을 바탕으로 '내일', '이번 주 금요일', '다음 주'와 같은 상대적인 시간 개념을 실제 캘린더 날짜(YYYY-MM-DD)와 시간으로 변환해서 마감기한(마감기한)에 반영하세요.

입력된 어수선한 업무/회의 텍스트를 논리적으로 분석하여, 아래 규격의 순수 JSON 포맷으로만 응답하세요.
단, ```json 등과 같은 마크다운 기호나 여분의 설명은 절대로 붙이지 마세요.

응답 필수 JSON 구조 (이 형태를 100% 준수할 것):
{{
  "summary": "회의 핵심 내용 1~2줄로 요약",
  "share_draft": "안녕하세요 팀원 여러분! 오늘 업무/회의에서 결정된 주요 사항과 담당자별 다음 할 일(Action Item)을 아래와 같이 정리하여 전달해 드립니다. 업무에 참고 부탁드립니다. (여기에 자연스럽게 줄바꿈과 텍스트 내용을 이어 붙여서, 사용자가 바로 복사해서 슬랙에 보낼 수 있는 아주 정중하고 완성된 공유용 텍스트)",
  "tasks": [
    {{
      "업무": "누가 봐도 이해할 수 있는 구체적인 행동(Action) 단위의 할 일",
      "담당자": "해당 업무를 수행해야 할 담당자 이름 또는 직급 (파악 불가 시 '미정')",
      "마감기한": "업무 마감 기한 (상대적 날짜를 절대적 캘린더 날짜/시간으로 변환하여 기재. 예: 2026-03-20 오후 6시. 언급이 없으면 '미정')",
      "마감기한_iso": "기재된 날짜 데이터를 ISO 시각화 (예: 2026-03-20T18:00:00). 날짜만 명시됐다면 T09:00:00 부착, 정보 전혀 없으면 '미정' 입력",
      "우선순위": "높음/중간/낮음 중 하나로 중요도 판별"
    }}
  ]
}}
"""
    try:
        # 모델 설정 (가볍고 빠르며, json 응답 모드를 지원하는 파라미터 적용)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_prompt,
            generation_config={"response_mime_type": "application/json"} # API 통신 안정성을 위한 Json Mime-type
        )
        
        # 비동기 AI 호출 (대기 시간 단축 효과)
        response = await model.generate_content_async(req.text)
        
        # AI가 준 텍스트 리턴값을 json 라이브러리로 안전하게 파싱
        result_text = response.text
        parsed_data = json.loads(result_text)
        
        # Pydantic 모델에 넣어서 한 번 더 검증하고 반환
        return WorkResponse(**parsed_data)

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="오류: AI가 올바른 JSON 형식을 반환하지 않았습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 분석 중 구글 서버 오류 발생: {str(e)}")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Clush AI Work Assistant Backend (FastAPI + Gemini) 서버가 정상 작동 중입니다."}

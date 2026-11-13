import streamlit as st
from openai import OpenAI
import anthropic
from google import genai
from datetime import datetime

st.set_page_config(page_title="AI 난장토론", page_icon="🎙️", layout="centered")

def secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

# 기존 Streamlit Secrets의 접속 비밀번호 설정을 그대로 사용
APP_PASSWORD = secret("APP_PASSWORD")
if APP_PASSWORD and not st.session_state.get("authenticated", False):
    st.title("🔐 AI 난장토론")
    entered = st.text_input("접속 비밀번호", type="password")
    if st.button("입장", type="primary"):
        if entered == APP_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 맞지 않습니다.")
    st.stop()

st.title("🎙️ AI 난장토론")
st.caption("세 AI가 한 번에 한 명씩 발언하며 실시간으로 주고받는 예능 토론")

AGENTS = {
    "ChatGPT": {"role": "말빨이 좋고 자신감 넘치는 논객. 상대의 말꼬리를 잡고 재치 있게 반박한다.", "emoji": "🤖", "stance": "이번 토론에서는 '닭이 먼저다'라는 입장을 맡아라."},
    "Claude": {"role": "냉철하고 논리적인 팩트 폭격기. 차분하지만 뼈 있는 한마디를 던진다.", "emoji": "🧠", "stance": "이번 토론에서는 '달걀이 먼저다'라는 입장을 맡아라. 진화론과 생물학적 근거를 활용하라."},
    "Gemini": {"role": "엉뚱하고 예측 불가능한 예능 캐릭터. 기상천외한 비유와 제3의 관점을 제시한다.", "emoji": "✨", "stance": "처음에는 중립적으로 양쪽을 듣고, 이후 독창적인 제3의 관점으로 끼어들어라."},
}

with st.sidebar:
    st.header("토론 설정")
    cycles = st.selectbox("토론 라운드", [1, 2, 3], index=2, help="첫 의견 발표 후, 각 라운드마다 세 AI가 한 명씩 번갈아 반박합니다.")
    st.markdown("---")
    st.subheader("사용 모델")
    openai_model = st.text_input("ChatGPT 모델 ID", value=secret("OPENAI_MODEL", "gpt-5.5"))
    claude_model = st.text_input("Claude 모델 ID", value=secret("CLAUDE_MODEL", "claude-sonnet-5-5"))
    gemini_model = st.text_input("Gemini 모델 ID", value=secret("GEMINI_MODEL", "gemini-3.8-flash"))
    st.markdown("---")
    st.caption("API 키와 접속 비밀번호는 기존 Streamlit Secrets에서 읽어옵니다.")

topic = st.text_input("오늘의 토론 주제", value="닭이 먼저인가, 달걀이 먼저인가?")
goal = st.text_input("토론 목표 (선택)", value="서로의 논리를 무너뜨리고, 가장 설득력 있고 웃긴 토론 승자를 가린다.")
conditions = st.text_area("추가 조건 (선택)", value=(
    "[프로그램 콘셉트: AI 난장토론]\n"
    "과거 지상파 TV 토론 프로그램을 패러디한 예능이다. 보고서나 발표문처럼 말하지 말고 실제 패널처럼 자연스럽게 말한다.\n"
    "상대방의 발언을 구체적으로 인용해 반박하고, 빈정거림·말장난·과장된 리액션·재치 있는 비유를 자연스럽게 활용한다.\n"
    "서로 무조건 동의하지 말고 의견 충돌을 만든다. 억지로 웃기려 하지 말고 핵심을 짧고 강렬하게 전달한다.\n"
    "ChatGPT는 닭파, Claude는 달걀파, Gemini는 중립에서 출발해 제3의 관점을 제시한다. 과학적 사실과 농담을 구분하고 사실을 꾸며내지 않는다."
), height=165)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "chat_started" not in st.session_state:
    st.session_state.chat_started = False
if "debate_completed" not in st.session_state:
    st.session_state.debate_completed = False


def get_keys():
    return {"openai": secret("OPENAI_API_KEY"), "anthropic": secret("ANTHROPIC_API_KEY"), "gemini": secret("GEMINI_API_KEY")}


def call_model(name, history):
    keys = get_keys()
    agent = AGENTS[name]
    system = (
        f"너는 AI 난장토론의 패널 {name}이다. 캐릭터: {agent['role']}\n"
        f"이번 토론에서의 입장: {agent['stance']}\n\n"
        "대화 규칙:\n"
        "1. 직전 발언뿐 아니라 지금까지의 전체 대화를 읽고 반응하라.\n"
        "2. 매번 새로운 발언 한 번만 하라. 혼자 여러 차례 말하지 마라.\n"
        "3. 상대의 이름을 부르거나 실제 발언을 짚어 직접 대화하라.\n"
        "4. 질문에 답하고, 허점이 보이면 반박하고, 필요하면 재치 있게 끼어들어라.\n"
        "5. 유쾌하고 생생하게 말하되 한 번의 발언은 한국어 2~5문장으로 제한하라.\n"
        "6. 보고서식 소제목이나 '첫째, 둘째' 구조를 쓰지 마라.\n"
        "7. 토론을 혼자 끝내거나 최종 결론을 내리지 마라. 지금은 네 차례 발언만 하라.\n"
        "8. 상대가 하지 않은 말을 지어내지 마라.\n\n"
        f"추가 프로그램 규칙:\n{conditions}"
    )
    transcript = "\n\n".join(f"{m['speaker']}: {m['content']}" for m in history)
    user_prompt = (
        f"토론 주제: {topic}\n토론 목표: {goal or '재미있고 설득력 있는 토론'}\n\n"
        f"지금까지의 대화:\n{transcript if transcript else '(아직 발언이 없습니다.)'}\n\n"
        f"지금은 {name}의 발언 차례다. 앞선 발언에 직접 반응하며 네 차례 발언만 해라."
    )
    if name == "ChatGPT":
        result = OpenAI(api_key=keys["openai"]).responses.create(model=openai_model, instructions=system, input=user_prompt, max_output_tokens=450)
        return result.output_text.strip()
    if name == "Claude":
        result = anthropic.Anthropic(api_key=keys["anthropic"]).messages.create(model=claude_model, max_tokens=450, system=system, messages=[{"role": "user", "content": user_prompt}])
        return "\n".join(x.text for x in result.content if getattr(x, "type", "") == "text").strip()
    result = genai.Client(api_key=keys["gemini"]).models.generate_content(model=gemini_model, contents=user_prompt, config={"system_instruction": system, "max_output_tokens": 450})
    return (result.text or "응답이 비어 있습니다.").strip()

st.markdown("---")
st.subheader("💬 실시간 토론")
for message in st.session_state.chat_messages:
    with st.chat_message("assistant", avatar=AGENTS[message["speaker"]]["emoji"]):
        st.markdown(f"**{message['speaker']}**")
        st.markdown(message["content"])

if st.button("🚀 AI 난장토론 시작", type="primary", use_container_width=True):
    missing = [key for key, value in get_keys().items() if not value]
    if not topic.strip():
        st.warning("토론 주제를 입력해 주세요.")
    elif missing:
        st.error("Streamlit Secrets에 API 키가 누락되었습니다: " + ", ".join(missing))
    else:
        st.session_state.chat_messages = []
        st.session_state.chat_started = True
        st.session_state.debate_completed = False
        st.rerun()

if st.session_state.chat_started and not st.session_state.debate_completed:
    # 오프닝은 각자 한 번씩. 이후에는 직전 대화 전체를 읽고 한 명씩 순서대로 응답.
    turn_order = ["ChatGPT", "Claude", "Gemini"]
    for _ in range(cycles):
        turn_order.extend(["Claude", "Gemini", "ChatGPT"])
    progress = st.progress(0, text="토론 패널 입장 중...")
    total = len(turn_order)
    for index, speaker in enumerate(turn_order):
        with st.chat_message("assistant", avatar=AGENTS[speaker]["emoji"]):
            st.markdown(f"**{speaker}**")
            with st.spinner(f"{speaker}가 앞선 발언에 답변하는 중..."):
                try:
                    answer = call_model(speaker, st.session_state.chat_messages)
                except Exception as error:
                    answer = f"⚠️ 응답 실패: `{type(error).__name__}: {error}`\n\nAPI 키, 모델 ID, 결제 및 사용 한도를 확인해 주세요."
            st.markdown(answer)
        st.session_state.chat_messages.append({"speaker": speaker, "content": answer, "time": datetime.now().strftime("%H:%M:%S")})
        progress.progress((index + 1) / total, text=f"{speaker} 발언 완료 ({index + 1}/{total})")
    progress.empty()
    st.session_state.debate_completed = True
    st.success("토론이 끝났습니다! 전체 대화를 저장할 수 있어요.")
    st.rerun()

if st.session_state.debate_completed:
    st.subheader("🏁 토론 종료")
    st.info("토론이 끝났습니다. 가장 설득력 있는 주장과 가장 웃겼던 발언을 직접 골라보세요.")
    transcript = "\n\n".join(f"--- {m['speaker']} ({m['time']}) ---\n{m['content']}" for m in st.session_state.chat_messages)
    st.download_button("📥 토론 전체 기록 다운로드 (.txt)", transcript, file_name="AI_난장토론_기록.txt", mime="text/plain", use_container_width=True)
    if st.button("🔄 새 토론 시작", use_container_width=True):
        st.session_state.chat_messages = []
        st.session_state.chat_started = False
        st.session_state.debate_completed = False
        st.rerun()

st.markdown("---")
st.caption("각 발언은 해당 AI 회사의 API를 개별 호출합니다. 발언 횟수와 길이에 따라 API 사용료가 발생합니다.")

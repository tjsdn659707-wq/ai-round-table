import streamlit as st
from openai import OpenAI
import anthropic
from google import genai

st.set_page_config(page_title="AI Round Table", page_icon="🗣️", layout="wide")

# Read API keys from Streamlit's private Secrets store.
def secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

# Optional simple password gate. Set APP_PASSWORD in Streamlit Secrets.
APP_PASSWORD = secret("APP_PASSWORD")
if APP_PASSWORD:
    if not st.session_state.get("authenticated", False):
        st.title("🔐 AI Round Table")
        entered = st.text_input("접속 비밀번호", type="password")
        if st.button("입장", type="primary"):
            if entered == APP_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("비밀번호가 맞지 않습니다.")
        st.stop()

st.title("🗣️ AI ROUND TABLE")
st.caption("ChatGPT · Claude · Gemini | 세 AI가 독립적으로 의견을 내고, 서로 반박하고, 결론을 도출합니다.")

with st.sidebar:
    st.header("토론 설정")
    rounds = st.selectbox("토론 라운드", [1, 2, 3], index=1,
                          help="1=의견 제시, 2=상호 비판, 3=재반박까지 진행")
    st.markdown("---")
    st.subheader("사용 모델")
    openai_model = st.text_input("ChatGPT 모델 ID", value=secret("OPENAI_MODEL", "gpt-5.5"))
    claude_model = st.text_input("Claude 모델 ID", value=secret("CLAUDE_MODEL", "claude-sonnet-5-5"))
    gemini_model = st.text_input("Gemini 모델 ID", value=secret("GEMINI_MODEL", "gemini-3.8-flash"))
    st.markdown("---")
    st.caption("API 키는 이 화면에 표시되지 않습니다. 사이트 관리자가 Streamlit Secrets에 안전하게 등록합니다.")

topic = st.text_area("토론 주제", placeholder="예: 90초 안에 만들 수 있는 가장 신기한 연금술 음식 영상은?", height=90)
goal = st.text_input("토론 목표 (선택)", placeholder="예: 실제로 만들 수 있고 시청자가 끝까지 볼 만한 아이디어 1개 선정")
conditions = st.text_area("추가 조건 (선택)", placeholder="예: 예산 3만 원 이하, 혼자 촬영, 안전한 식재료만 사용", height=75)

agents = [
    ("ChatGPT", "창의적인 전략가. 새로운 아이디어와 구체적인 실행 방법을 제안한다."),
    ("Claude", "논리적인 비평가. 허점과 위험을 찾아내고 더 나은 대안을 제시한다."),
    ("Gemini", "확장형 분석가. 관점을 넓히고 현실성, 차별성, 대중성을 검토한다."),
]

def get_keys():
    return {
        "openai": secret("OPENAI_API_KEY"),
        "anthropic": secret("ANTHROPIC_API_KEY"),
        "gemini": secret("GEMINI_API_KEY"),
    }

def ask_agent(name, role, prompt):
    keys = get_keys()
    system = (
        f"너는 AI ROUND TABLE의 참가자 {name}이다. {role} "
        "한국어로 답하고, 구체적인 근거와 실행 가능한 제안을 제시하라. "
        "다른 AI의 의견에 무조건 동의하지 말고 필요하면 분명하게 반박하라. "
        "사실이 불확실하면 불확실하다고 밝혀라. 답변은 핵심 위주로 작성하라."
    )
    if name == "ChatGPT":
        client = OpenAI(api_key=keys["openai"])
        result = client.responses.create(
            model=openai_model,
            instructions=system,
            input=prompt,
            max_output_tokens=1200
        )
        return result.output_text
    if name == "Claude":
        client = anthropic.Anthropic(api_key=keys["anthropic"])
        result = client.messages.create(
            model=claude_model,
            max_tokens=1200,
            system=system,
            messages=[{"role": "user", "content": prompt}]
        )
        return "\n".join(x.text for x in result.content if getattr(x, "type", "") == "text")
    client = genai.Client(api_key=keys["gemini"])
    result = client.models.generate_content(
        model=gemini_model,
        contents=prompt,
        config={"system_instruction": system, "max_output_tokens": 1200}
    )
    return result.text or "응답이 비어 있습니다."

def debate_round(label, prompt):
    st.subheader(label)
    cols = st.columns(3)
    answers = {}
    for col, (name, role) in zip(cols, agents):
        with col:
            st.markdown(f"### {name}")
            with st.spinner(f"{name}가 생각하는 중..."):
                try:
                    answer = ask_agent(name, role, prompt)
                    answers[name] = answer
                    st.markdown(answer)
                except Exception as e:
                    answers[name] = f"오류: {type(e).__name__}: {e}"
                    st.error(f"{name} 응답 실패")
                    st.caption("API 키, 모델 ID, 결제/사용 한도 또는 API 접근 권한을 확인해 주세요.")
    return answers

if st.button("🚀 세 AI 토론 시작", type="primary", use_container_width=True):
    keys = get_keys()
    missing = [label for label, value in [
        ("OPENAI_API_KEY", keys["openai"]),
        ("ANTHROPIC_API_KEY", keys["anthropic"]),
        ("GEMINI_API_KEY", keys["gemini"]),
    ] if not value]
    if not topic.strip():
        st.warning("먼저 토론 주제를 입력해 주세요.")
    elif missing:
        st.error("관리자가 Streamlit Secrets에 API 키를 등록해야 합니다: " + ", ".join(missing))
    else:
        st.session_state["debate"] = []
        base = (
            f"토론 주제: {topic}\n"
            f"토론 목표: {goal or '가장 설득력 있고 유용한 결론 도출'}\n"
            f"추가 조건: {conditions or '없음'}"
        )
        with st.container():
            st.session_state["debate"].append((
                "ROUND 1 · 독립 의견",
                debate_round(
                    "ROUND 1 · 독립 의견",
                    base + "\n\n다른 참가자의 의견을 아직 모른다고 가정하고 독립적인 입장을 제시하라. "
                    "핵심 주장, 이유, 구체적인 실행안, 예상되는 단점을 포함하라."
                )
            ))
        if rounds >= 2:
            all_previous = "\n\n".join(
                f"[{stage}]\n" + "\n\n".join(f"{n}:\n{a}" for n, a in result.items())
                for stage, result in st.session_state["debate"]
            )
            st.session_state["debate"].append((
                "ROUND 2 · 상호 비판",
                debate_round(
                    "ROUND 2 · 상호 비판",
                    base + "\n\n" + all_previous +
                    "\n\n위의 모든 의견을 검토하고 다른 참가자의 주장 중 동의하는 점, 반박하는 점, "
                    "놓친 관점, 개선안을 구분해 답하라. 구체적인 근거를 들어 토론하라."
                )
            ))
        if rounds >= 3:
            all_previous = "\n\n".join(
                f"[{stage}]\n" + "\n\n".join(f"{n}:\n{a}" for n, a in result.items())
                for stage, result in st.session_state["debate"]
            )
            st.session_state["debate"].append((
                "ROUND 3 · 재반박 및 입장 수정",
                debate_round(
                    "ROUND 3 · 재반박 및 입장 수정",
                    base + "\n\n" + all_previous +
                    "\n\n앞선 비판에 답하라. 자신의 기존 주장을 유지할지 수정할지 분명히 밝히고, "
                    "상대의 좋은 지적을 반영해 최종 제안을 개선하라."
                )
            ))
        all_previous = "\n\n".join(
            f"[{stage}]\n" + "\n\n".join(f"{n}:\n{a}" for n, a in result.items())
            for stage, result in st.session_state["debate"]
        )
        st.session_state["debate"].append((
            "FINAL · 최종 판단",
            debate_round(
                "FINAL · 최종 판단",
                base + "\n\n" + all_previous +
                "\n\n전체 토론을 바탕으로 최종 판단을 작성하라. "
                "최종 추천안, 추천 이유, 남은 이견, 실행할 다음 단계를 정리하라. "
                "억지로 합의하지 말고 세 참가자의 관점 차이를 인정하라."
            )
        ))

if st.session_state.get("debate"):
    st.divider()
    st.header("토론 기록")
    for stage, answers in st.session_state["debate"]:
        with st.expander(stage, expanded=True):
            tabs = st.tabs(list(answers.keys()))
            for tab, (name, answer) in zip(tabs, answers.items()):
                with tab:
                    st.markdown(answer)
    transcript = "\n\n".join(
        f"\n{'='*16} {stage} {'='*16}\n" +
        "\n\n".join(f"--- {name} ---\n{answer}" for name, answer in answers.items())
        for stage, answers in st.session_state["debate"]
    )
    st.download_button("토론 기록 다운로드 (.txt)", transcript,
                       file_name="AI_Round_Table_토론기록.txt", mime="text/plain",
                       use_container_width=True)

st.markdown("---")
st.caption("안내: 각 AI는 해당 회사의 API로 별도 호출됩니다. ChatGPT·Claude·Gemini의 일반 웹 구독과 API 요금은 별개일 수 있습니다. 여러 라운드를 실행하면 API 사용료가 발생합니다.")

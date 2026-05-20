# -*- coding: utf-8 -*-
from pathlib import Path
import sys
import importlib.util

import streamlit as st


# =========================
# App Config
# =========================
APP_DIR = Path(__file__).resolve().parent
UNIFIED_FILE = APP_DIR / "Unified assistant.py"

sys.path.insert(0, str(APP_DIR))


def load_unified_assistant():
    spec = importlib.util.spec_from_file_location("unified_assistant_module", UNIFIED_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@st.cache_resource
def get_assistant():
    return load_unified_assistant()


assistant = get_assistant()


st.set_page_config(
    page_title="Oil Spill Unified Assistant",
    page_icon="🛢️",
    layout="wide"
)


st.title("🛢️ Oil Spill Unified Assistant")
st.caption("SQL Agent + RAG + Hybrid Router for Oil Spill Analysis")


with st.sidebar:
    st.header("⚙️ Settings")
    show_details = st.toggle("Show route details", value=True)
    show_sources = st.toggle("Show RAG sources", value=True)

    st.markdown("---")
    st.subheader("Examples")

    example_1 = "كم عدد التسربات الحرجة؟"
    example_2 = "تأثير تسربات النفط على الأسماك"
    example_3 = "أخطر تسرب عندي وش التوصية المناسبة للتعامل معه؟"

    if st.button("SQL Example"):
        st.session_state["pending_question"] = example_1

    if st.button("RAG Example"):
        st.session_state["pending_question"] = example_2

    if st.button("Hybrid Example"):
        st.session_state["pending_question"] = example_3

    st.markdown("---")
    st.info(
        "SQL للأسئلة الرقمية من قاعدة البيانات.\n\n"
        "RAG للأسئلة المعرفية من ملفات PDF.\n\n"
        "Hybrid للأسئلة التي تحتاج الاثنين."
    )


if "messages" not in st.session_state:
    st.session_state.messages = []


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant" and show_details and msg.get("details"):
            details = msg["details"]

            with st.expander("Route details"):
                st.write("Selected route:", details.get("route"))
                st.write("Reason:", details.get("route_reason"))

                if details.get("sql_answer"):
                    st.markdown("### SQL Answer")
                    st.markdown(details["sql_answer"])

                if details.get("rag_answer"):
                    st.markdown("### RAG Answer")
                    st.markdown(details["rag_answer"])

                if show_sources and details.get("rag_sources"):
                    st.markdown("### RAG Sources")
                    for source in details["rag_sources"]:
                        st.write(
                            f"- {source.get('source')} "
                            f"(page {source.get('page')}) "
                            f"score={source.get('score')}"
                        )


pending_question = st.session_state.pop("pending_question", None)
user_question = pending_question or st.chat_input("اكتب سؤالك هنا...")


if user_question:
    st.session_state.messages.append({
        "role": "user",
        "content": user_question
    })

    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                result = assistant.answer_unified(user_question, verbose=False)

                route = result.get("route", "unknown")
                final_answer = result.get("final_answer", "")

                if show_details:
                    if route == "sql":
                        st.success("Route: SQL Database Agent")
                    elif route == "rag":
                        st.info("Route: RAG Documents Agent")
                    elif route == "hybrid":
                        st.warning("Route: Hybrid SQL + RAG")
                    else:
                        st.write(f"Route: {route}")

                st.markdown(final_answer)

                if show_details:
                    with st.expander("Full details"):
                        st.write("Route:", result.get("route"))
                        st.write("Reason:", result.get("route_reason"))

                        if result.get("sql_answer"):
                            st.markdown("### SQL Answer")
                            st.markdown(result["sql_answer"])

                        if result.get("rag_answer"):
                            st.markdown("### RAG Answer")
                            st.markdown(result["rag_answer"])

                        if show_sources and result.get("rag_sources"):
                            st.markdown("### RAG Sources")
                            for source in result["rag_sources"]:
                                st.write(
                                    f"- {source.get('source')} "
                                    f"(page {source.get('page')}) "
                                    f"score={source.get('score')}"
                                )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_answer,
                    "details": result
                })

            except Exception as e:
                error_msg = f"حدث خطأ أثناء تشغيل المساعد:\n\n`{e}`"
                st.error(error_msg)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                    "details": None
                })

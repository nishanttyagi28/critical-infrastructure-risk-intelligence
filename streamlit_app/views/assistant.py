"""Operations analyst. Answers from the warehouse, and from an LLM when configured."""

import streamlit as st

from ciri.llm.analyst import answer_question
from common import render_sidebar, require_warehouse

store = require_warehouse()
render_sidebar(store)

st.title("AI assistant")
st.caption(
    "Answers are computed from the warehouse. "
    "Set OPENAI_API_KEY and, if needed, OPENAI_BASE_URL to send the same brief to an OpenAI-compatible model."
)

examples = [
    "Which regions have the highest outage risk?",
    "What caused most failures this month?",
    "Which assets require preventive maintenance?",
    "What is the projected demand next quarter?",
    "Give me an executive summary.",
]
picked = st.pills("Examples", examples, selection_mode="single")
question = st.text_area("Question", value=picked or examples[0], height=80)
if st.button("Ask", type="primary"):
    with st.spinner("Reading the warehouse"):
        result = answer_question(question, store)
    st.write(result.answer)
    st.subheader("Recommendations")
    for item in result.recommendations:
        st.write(f"- {item}")
    st.caption(f"Source: {result.source}")
    with st.expander("Context sent with the question"):
        st.code(result.context)

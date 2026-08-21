"""
Streamlit chat UI for the Family Matching Agent — Macknificient World
Resource Navigator.

A single-page chat interface, styled to match mackworldinc.org's brand
(deep green / mint / gold), that a case worker or parent can use
directly. Wraps matching_agent.build_agent() and keeps the conversation
(and the Strands Agent's own message history) alive across turns via
st.session_state.

Run with:
    streamlit run app.py
"""

import sqlite3
from pathlib import Path

import streamlit as st

from matching_agent import build_agent

DB_PATH = Path(__file__).parent / "resources.db"

st.set_page_config(
    page_title="Macknificient World Resource Navigator",
    page_icon="\U0001f30f",
    layout="centered",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Inter:wght@400;500;600;700&display=swap');

:root {
  --mw-green-dark: #1f5c3e;
  --mw-green-mid: #2f7d57;
  --mw-bg-mint: #e7f3e2;
  --mw-orange: #e5a83d;
  --mw-cream: #fbf3e7;
  --mw-text: #1f2a24;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: var(--mw-text);
}

.stApp {
    background-color: var(--mw-bg-mint);
}

section[data-testid="stSidebar"] {
    background-color: var(--mw-cream);
}

.mw-header {
    text-align: center;
    padding: 1.25rem 0 0.5rem 0;
}
.mw-header h1 {
    font-family: 'Playfair Display', serif;
    font-weight: 700;
    color: var(--mw-green-dark);
    font-size: 2.1rem;
    margin-bottom: 0.15rem;
}
.mw-header .mw-script {
    font-family: 'Playfair Display', serif;
    font-style: italic;
    font-weight: 600;
    color: var(--mw-green-mid);
    font-size: 1.25rem;
}
.mw-pill {
    display: inline-block;
    background: white;
    color: var(--mw-green-dark);
    border-radius: 999px;
    padding: 0.35rem 1.1rem;
    font-size: 0.82rem;
    font-weight: 600;
    margin-top: 0.7rem;
    border: 1px solid var(--mw-green-mid);
}
.mw-banner {
    background: var(--mw-orange);
    color: white;
    text-align: center;
    font-style: italic;
    font-family: 'Playfair Display', serif;
    padding: 0.55rem;
    border-radius: 8px;
    margin: 1rem 0 1.5rem 0;
}

[data-testid="stChatMessage"] {
    background: white;
    border-radius: 14px;
    border: 1px solid #d9e8d2;
}

div.stButton > button, div.stDownloadButton > button {
    background-color: var(--mw-green-dark);
    color: white;
    border-radius: 999px;
    border: none;
}
div.stButton > button:hover, div.stDownloadButton > button:hover {
    background-color: var(--mw-green-mid);
    color: white;
}

.mw-sidebar-card {
    background: white;
    border-radius: 10px;
    padding: 0.6rem 0.8rem;
    margin-bottom: 0.5rem;
    border: 1px solid #ecd9b8;
}
.mw-sidebar-card .mw-name {
    font-weight: 600;
    color: var(--mw-green-dark);
    font-size: 0.9rem;
}
.mw-sidebar-card .mw-meta {
    font-size: 0.78rem;
    color: #5a6b60;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="mw-header">
      <h1>Macknificient World Resource Navigator</h1>
      <div class="mw-script">Create, Connect &amp; Conquer</div>
      <div class="mw-pill">Mental Health &middot; Neurodivergent Support &middot; Financial Aid &middot; Youth Activities</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="mw-banner">Describe a family\'s situation below &mdash; get a ranked, '
    "explained shortlist of vetted Tampa Bay / Hillsborough County resources.</div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### About")
    st.write(
        "Built for Macknificient World's case workers and the families they "
        "serve. Describe a child's age, needs, zip code, and any constraints "
        "(cost, transportation, language) in plain language."
    )
    st.markdown("### Recently added by our Discovery Agent")
    st.caption("Proof this isn't a static list — new finds appear here automatically.")
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        recent = conn.execute(
            "SELECT name, category, confidence FROM resources "
            "ORDER BY created_at DESC LIMIT 3"
        ).fetchall()
        conn.close()
        for r in recent:
            st.markdown(
                f"""<div class="mw-sidebar-card">
                    <div class="mw-name">{r['name']}</div>
                    <div class="mw-meta">{r['category'].replace('_', ' ')} &middot; confidence: {r['confidence']}</div>
                </div>""",
                unsafe_allow_html=True,
            )
    if st.button("Clear conversation"):
        st.session_state.pop("agent", None)
        st.session_state.pop("history", None)
        st.rerun()

if "agent" not in st.session_state:
    st.session_state.agent = build_agent()
if "history" not in st.session_state:
    st.session_state.history = []

for role, text in st.session_state.history:
    avatar = "\U0001f9ed" if role == "assistant" else None
    with st.chat_message(role, avatar=avatar):
        st.markdown(text)

prompt = st.chat_input(
    "e.g. \"8-year-old with ADHD, family struggling with rent, wants him in a sport, zip 33610\""
)
if prompt:
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="\U0001f9ed"):
        with st.spinner("Searching vetted Tampa Bay resources..."):
            result = st.session_state.agent(prompt)
            text = str(result)
        st.markdown(text)
    st.session_state.history.append(("assistant", text))

if st.session_state.history:
    transcript = "\n\n".join(
        f"{'You' if r == 'user' else 'Resource Navigator'}: {t}"
        for r, t in st.session_state.history
    )
    st.download_button(
        "Download shortlist as text",
        data=transcript,
        file_name="macknificient_world_shortlist.txt",
        mime="text/plain",
    )

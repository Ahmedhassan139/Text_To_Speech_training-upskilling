# app.py
# Streamlit Text -> Audio (MP3) using Microsoft Edge-TTS (neural voices)

import asyncio
import tempfile
from pathlib import Path

import streamlit as st
import edge_tts


# ----------------------------
# Styling (All-Blue Gradient Theme)
# ----------------------------
st.set_page_config(
    page_title="Text to Audio Tool for Training and Upskilling",
    page_icon="🔊",
    layout="centered"
)

st.markdown(
    """
<style>
:root{
  --blue-dark:#003781;
  --blue-main:#005fcc;
  --blue-light:#eaf2ff;
  --blue-soft:#f3f7ff;
}
.stApp { background: linear-gradient(180deg, var(--blue-soft), white); }
.block-container { max-width: 920px; padding-top: 2rem; }
.header{
  background: linear-gradient(135deg, var(--blue-dark), var(--blue-main));
  color: white; padding: 20px 22px; border-radius: 18px;
  font-weight: 800; font-size: 22px;
  box-shadow: 0 12px 28px rgba(0,0,0,.15);
  margin-bottom: 18px;
}
.card{
  background: white; border-radius: 18px; padding: 18px 20px;
  box-shadow: 0 8px 26px rgba(0,56,129,.12);
  margin-bottom: 18px;
}
.stButton>button{
  background: linear-gradient(135deg, var(--blue-dark), var(--blue-main)) !important;
  color: white !important;
  border-radius: 14px !important;
  font-weight: 800 !important;
  border: none !important;
}
.stSlider > div { color: var(--blue-dark); }
.stSelectbox label, .stTextArea label, .stSlider label {
  color: var(--blue-dark);
  font-weight: 700;
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="header">Text to Audio Tool for Training and Upskilling</div>',
    unsafe_allow_html=True
)


# ----------------------------
# Async helper (Streamlit Cloud safe)
# ----------------------------
def run_async(coro):
    """
    Run an async coroutine safely in Streamlit (works even if an event loop is already running).
    """
    try:
        loop = asyncio.get_running_loop()
        # If we get here, a loop is already running -> run in a new loop
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    except RuntimeError:
        # No running loop
        return asyncio.run(coro)


# ----------------------------
# Helpers
# ----------------------------
def pct_to_edge_rate(pct: int) -> str:
    # slider 100..250 -> map to -50%..+50%
    val = int(round(((pct - 175) / 75) * 50))
    val = max(-50, min(50, val))
    return f"{val:+d}%"

def volume_to_edge(vol: float) -> str:
    # 0..1 -> -50%..+0%
    val = int(round((vol - 1.0) * 50))
    val = max(-50, min(0, val))
    return f"{val:+d}%"

@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_voices_cached():
    # Cache voices for 24h (faster on Cloud)
    return run_async(edge_tts.list_voices())

def filter_voice_list(voices, prefer_lang="en-US", prefer_female=True):
    out = []
    for v in voices:
        locale = v.get("Locale", "")
        gender = (v.get("Gender", "") or "").lower()
        if prefer_lang and locale != prefer_lang:
            continue
        if prefer_female and gender != "female":
            continue
        out.append(v)

    # fallback
    if not out:
        out = [v for v in voices if v.get("Locale") == prefer_lang] if prefer_lang else voices
    if not out:
        out = voices
    return out

async def synthesize_edge_tts(text: str, voice_short_name: str, rate_str: str, volume_str: str, out_path: Path):
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice_short_name,
        rate=rate_str,
        volume=volume_str,
    )
    await communicate.save(str(out_path))


# ----------------------------
# UI
# ----------------------------
st.markdown('<div class="card">', unsafe_allow_html=True)

c1, c2 = st.columns([1, 1])
with c1:
    prefer_lang = st.selectbox("Language", ["en-US", "Any"], index=0)
with c2:
    prefer_gender = st.selectbox("Preferred voice", ["Female", "Any"], index=0)

voices = get_voices_cached()
filtered = filter_voice_list(
    voices,
    prefer_lang=None if prefer_lang == "Any" else prefer_lang,
    prefer_female=(prefer_gender == "Female")
)

def nice_label(v):
    sn = v.get("ShortName", "")
    locale = v.get("Locale", "")
    gender = v.get("Gender", "")
    name_part = sn.split("-")[-1] if "-" in sn else sn
    if name_part.lower().endswith("neural"):
        base = name_part[:-6]
        display = f"{base} (Neural)"
    else:
        display = name_part
    return f"{display} — {locale} — {gender}"

voice_map = {nice_label(v): v for v in filtered}

# Default: prefer Jenny/Aria if available
default_label = None
for key in voice_map.keys():
    if "jenny" in key.lower():
        default_label = key
        break
if default_label is None:
    for key in voice_map.keys():
        if "aria" in key.lower():
            default_label = key
            break
if default_label is None:
    default_label = list(voice_map.keys())[0]

voice_choice = st.selectbox(
    "Voice",
    list(voice_map.keys()),
    index=list(voice_map.keys()).index(default_label)
)

text = st.text_area(
    "Text",
    height=160,
    value="This tool converts text into audio for training and upskilling purposes."
)

col1, col2, col3 = st.columns(3)
with col1:
    rate_slider = st.slider("Speech Rate", 100, 250, 180, step=5)
with col2:
    volume = st.slider("Volume", 0.0, 1.0, 1.0, step=0.05)
with col3:
    filename = st.text_input("File name", "training_audio.mp3")

st.markdown("</div>", unsafe_allow_html=True)

if "busy" not in st.session_state:
    st.session_state.busy = False

generate = st.button(
    "Generate Audio",
    type="primary",
    use_container_width=True,
    disabled=st.session_state.busy
)

if generate:
    if not text.strip():
        st.warning("Please enter some text.")
        st.stop()

    st.session_state.busy = True
    try:
        v = voice_map[voice_choice]
        voice_short = v.get("ShortName")

        rate_str = pct_to_edge_rate(rate_slider)
        volume_str = volume_to_edge(volume)

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.mp3"

            with st.spinner("Generating audio (Edge Neural TTS)..."):
                run_async(synthesize_edge_tts(text, voice_short, rate_str, volume_str, out_path))

            audio_bytes = out_path.read_bytes()
            if len(audio_bytes) < 2000:
                st.error("Generated audio is empty. Try a different voice.")
                st.stop()

            st.success("Audio generated successfully")
            st.audio(audio_bytes, format="audio/mp3")
            st.download_button(
                "Download Audio",
                data=audio_bytes,
                file_name=filename,
                mime="audio/mpeg",
                use_container_width=True
            )
    finally:
        st.session_state.busy = False

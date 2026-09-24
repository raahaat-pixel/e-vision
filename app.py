import json
import hashlib
import base64
import html
from datetime import datetime
from io import BytesIO
import streamlit as st
from PIL import Image, ImageOps
from google import genai
from google.genai import types
# ============================================================
# CONFIG
# ============================================================
st.set_page_config(
    page_title="Анализатор состава продуктов E-vision",
    page_icon=":material/science:",
    layout="wide",
)
# ============================================================
# CSS
# ============================================================
st.markdown(
    """
<style>
    :root {
        --ev-ink: #0b1220;
        --ev-muted: #64748b;
        --ev-blue: #1677ff;
        --ev-cyan: #18c8ff;
    }
    .stApp {
        min-height: 100vh;
        background:
            radial-gradient(circle at 8% 10%, rgba(22,119,255,.16), transparent 27%),
            radial-gradient(circle at 90% 16%, rgba(24,200,255,.14), transparent 25%),
            radial-gradient(circle at 55% 90%, rgba(99,102,241,.10), transparent 30%),
            linear-gradient(135deg, #f4f8ff 0%, #eef5ff 48%, #f8fbff 100%);
        color: var(--ev-ink);
    }
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 0;
        opacity: .27;
        background-image:
            radial-gradient(circle, rgba(22,119,255,.20) 1px, transparent 1.4px),
            linear-gradient(120deg, transparent 49.7%, rgba(24,200,255,.035) 50%, transparent 50.3%);
        background-size: 44px 44px, 190px 190px;
        mask-image: linear-gradient(to bottom, black 0%, transparent 82%);
    }

    [data-testid="stHeader"] {
        background: rgba(244,248,255,.58) !important;
        backdrop-filter: blur(18px) !important;
    }

    [data-testid="stToolbar"] {
        display: flex !important;
    }
    [data-testid="stToolbar"] a, 
    [data-testid="stToolbar"] button:not([aria-label="Main menu"]) {
        display: none !important;
    }

    #viewerBadge_container, 
    .viewerBadge_container, 
    .viewerBadge_link, 
    [data-testid="stViewerBadge"] {
        display: none !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    footer, 
    .stDeployButton {
        display: none !important;
    }


    .block-container {
        max-width: 1420px;
        padding-top: 4.2rem; /* Немного уменьшил отступ на десктопе, так как нет шапки */
        padding-bottom: 4rem;
        position: relative;
        z-index: 1;
    }
    .main-title {
        font-size: clamp(31px, 4vw, 48px);
        font-weight: 850;
        letter-spacing: -1.8px;
        line-height: 1.04;
        margin-bottom: 7px;
        background: linear-gradient(100deg, #07111f 5%, #1677ff 52%, #00a9dc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .subtitle {
        font-size: 16px;
        color: var(--ev-muted);
        margin-bottom: 22px;
    }
    /* SIDEBAR GLASS PANEL */
    [data-testid="stSidebar"] {
        background: transparent !important;
    }
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        height: 100% !important;
        max-height: 100vh !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        scrollbar-width: thin;
    }
    [data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar {
        width: 7px;
    }
    [data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar-thumb {
        background: rgba(100,116,139,.28);
        border-radius: 999px;
    }
    [data-testid="stSidebar"] > div:first-child {
        background:
            linear-gradient(135deg, rgba(245,249,255,.84), rgba(232,240,252,.70)) !important;
        border-right: 1px solid rgba(255,255,255,.94);
        border-top-right-radius: 30px;
        border-bottom-right-radius: 30px;
        box-shadow:
            10px 0 34px rgba(30,64,175,.07),
            inset -1px 0 0 rgba(120,160,220,.08);
        backdrop-filter: blur(24px) saturate(145%);
        -webkit-backdrop-filter: blur(24px) saturate(145%);
        overflow: hidden;
    }
    .section-kicker {
        color: #1677ff;
        font-size: 11px;
        font-weight: 850;
        letter-spacing: 2.2px;
        text-transform: uppercase;
        margin-bottom: 9px;
    }
    .glass-section-title {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 21px;
    }
    .glass-section-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        flex: 0 0 30px;
        border-radius: 50%;
        background: rgba(37,99,235,.10);
        border: 1px solid rgba(37,99,235,.15);
        color: #2563eb;
        font-size: 10px;
        font-weight: 850;
        box-shadow: inset 0 1px 0 rgba(255,255,255,.9);
    }
    .glass-section-name {
        font-size: clamp(25px, 3vw, 34px);
        font-weight: 850;
        letter-spacing: -1.2px;
        line-height: 1.12;
        color: #07111f;
    }
    .process-step {
        display: grid;
        grid-template-columns: 32px 1fr;
        column-gap: 12px;
        padding: 12px 0;
        border-bottom: 1px solid rgba(148,163,184,.13);
    }
    .process-step:last-child {
        border-bottom: 0;
        padding-bottom: 2px;
    }
    .process-number {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        background: rgba(255,255,255,.62);
        border: 1px solid rgba(255,255,255,.88);
        color: #2563eb;
        font-size: 10px;
        font-weight: 850;
        box-shadow:
            0 5px 16px rgba(30,64,175,.07),
            inset 0 1px 0 rgba(255,255,255,.9);
    }
    .process-title {
        font-size: 14px;
        font-weight: 800;
        color: #172033;
        margin-bottom: 4px;
    }
    .process-description {
        font-size: 12px;
        line-height: 1.55;
        color: #718096;
    }
    /* LIQUID GLASS */
    .st-key-ev-input-panel,
    .st-key-ev-process-panel {
        position: relative !important;
        overflow: hidden !important;
        border-radius: 30px !important;
        border: 1px solid rgba(255,255,255,.84) !important;
        background:
            radial-gradient(circle at 86% 16%, rgba(24,200,255,.22), transparent 22%),
            radial-gradient(circle at 8% 92%, rgba(22,119,255,.15), transparent 30%),
            linear-gradient(135deg, rgba(255,255,255,.76), rgba(255,255,255,.42)) !important;
        box-shadow:
            0 24px 70px rgba(30,64,175,.12),
            inset 0 1px 0 rgba(255,255,255,.95) !important;
        backdrop-filter: blur(26px) saturate(155%) !important;
        -webkit-backdrop-filter: blur(26px) saturate(155%) !important;
    }
    .st-key-ev-input-panel > div:first-child,
    .st-key-ev-process-panel > div:first-child {
        position: relative;
        z-index: 1;
        background: transparent !important;
        border: 0 !important;
    }
    .st-key-ev-input-panel::before,
    .st-key-ev-process-panel::before {
        content: "";
        position: absolute;
        width: 180px;
        height: 180px;
        right: -55px;
        bottom: -85px;
        border-radius: 50%;
        background: rgba(24,200,255,.14);
        filter: blur(12px);
        pointer-events: none;
    }
    .st-key-ev-input-panel::after,
    .st-key-ev-process-panel::after {
        content: "";
        position: absolute;
        width: 55%;
        height: 1px;
        left: 10%;
        top: 0;
        background: linear-gradient(
            90deg,
            transparent,
            rgba(255,255,255,.95),
            transparent
        );
        pointer-events: none;
    }
    .ev-hero {
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,.84);
        border-radius: 30px;
        padding: 32px;
        margin: 4px 0 24px;
        background:
            radial-gradient(circle at 86% 16%, rgba(24,200,255,.22), transparent 22%),
            radial-gradient(circle at 8% 92%, rgba(22,119,255,.15), transparent 30%),
            linear-gradient(135deg, rgba(255,255,255,.76), rgba(255,255,255,.42));
        box-shadow:
            0 24px 70px rgba(30,64,175,.12),
            inset 0 1px 0 rgba(255,255,255,.95);
        backdrop-filter: blur(26px) saturate(155%);
        -webkit-backdrop-filter: blur(26px) saturate(155%);
    }
    .ev-hero::before {
        content: "";
        position: absolute;
        width: 180px;
        height: 180px;
        right: -55px;
        bottom: -85px;
        border-radius: 50%;
        background: rgba(24,200,255,.14);
        filter: blur(12px);
    }
    .ev-hero::after {
        content: "";
        position: absolute;
        width: 55%;
        height: 1px;
        left: 10%;
        top: 0;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,.95), transparent);
    }
    .ev-kicker {
        color: #1677ff;
        font-size: 11px;
        font-weight: 850;
        letter-spacing: 2.2px;
        text-transform: uppercase;
        margin-bottom: 9px;
    }
    .ev-hero-title {
        font-size: clamp(25px, 3vw, 38px);
        font-weight: 850;
        letter-spacing: -1.2px;
        margin-bottom: 8px;
    }
    .ev-hero-text {
        max-width: 760px;
        color: #64748b;
        line-height: 1.65;
        font-size: 15px;
    }
    .workflow {
        display: flex;
        align-items: center;
        gap: 7px;
        flex-wrap: wrap;
        margin-top: 21px;
    }
    .workflow-step {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 9px 13px;
        border-radius: 999px;
        background: rgba(255,255,255,.55);
        border: 1px solid rgba(255,255,255,.82);
        box-shadow: 0 7px 20px rgba(30,64,175,.06), inset 0 1px 0 rgba(255,255,255,.9);
        color: #1455ad;
        font-size: 12px;
        font-weight: 780;
        letter-spacing: .01em;
        backdrop-filter: blur(12px);
    }
    .workflow-step b {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        border-radius: 50%;
        background: rgba(37,99,235,.10);
        border: 1px solid rgba(37,99,235,.14);
        color: #2563eb;
        font-size: 9px;
        font-weight: 850;
        letter-spacing: .02em;
    }
    .workflow-arrow {
        color: #8aa2bd;
        font-weight: 800;
    }
    .ev-analysis {
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,.86);
        border-radius: 24px;
        padding: 21px;
        margin: 18px 0;
        background:
            radial-gradient(circle at 90% 50%, rgba(24,200,255,.13), transparent 25%),
            rgba(255,255,255,.55);
        box-shadow:
            0 16px 45px rgba(30,64,175,.08),
            inset 0 1px 0 rgba(255,255,255,.92);
        backdrop-filter: blur(20px) saturate(145%);
    }
    .ev-analysis::before {
        content: "";
        position: absolute;
        top: 0;
        left: -30%;
        width: 25%;
        height: 2px;
        background: linear-gradient(90deg, transparent, #18c8ff, #1677ff, transparent);
        box-shadow: 0 0 18px rgba(24,200,255,.55);
        animation: ev-glass-scan 1.8s ease-in-out infinite;
    }
    @keyframes ev-glass-scan {
        0% { left: -30%; opacity: 0; }
        15% { opacity: 1; }
        85% { opacity: 1; }
        100% { left: 105%; opacity: 0; }
    }
    .ev-analysis-label {
        color: #1677ff;
        font-size: 10px;
        font-weight: 850;
        letter-spacing: 1.8px;
        text-transform: uppercase;
    }
    .ev-analysis-title {
        font-size: 19px;
        font-weight: 800;
        margin-top: 5px;
    }
    .ev-progress {
        height: 6px;
        margin-top: 15px;
        border-radius: 999px;
        overflow: hidden;
        background: rgba(148,163,184,.16);
    }
    .ev-progress > div {
        width: 68%;
        height: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, #1677ff, #18c8ff);
        box-shadow: 0 0 14px rgba(24,200,255,.35);
        animation: ev-progress 1.6s ease-in-out infinite;
        transform-origin: left;
    }
    @keyframes ev-progress {
        0%,100% { transform: scaleX(.22); opacity: .65; }
        50% { transform: scaleX(1); opacity: 1; }
    }
    .score-number {
        font-size: 58px;
        font-weight: 850;
        line-height: 1;
        margin: 8px 0 0;
        letter-spacing: -2px;
    }
    .verdict-title {
        font-size: 19px;
        font-weight: 780;
        line-height: 1.4;
    }
    .scale {
        position: relative;
        width: 100%;
        height: 14px;
        margin-top: 25px;
        border-radius: 999px;
        background: linear-gradient(90deg, #ef4444 0%, #f97316 25%, #facc15 50%, #a3e635 75%, #22c55e 100%);
        box-shadow: inset 0 1px 3px rgba(15,23,42,.16), 0 5px 18px rgba(22,119,255,.08);
    }
    .scale-marker {
        position: absolute;
        left: var(--score);
        top: 50%;
        width: 5px;
        height: 28px;
        transform: translate(-50%, -50%);
        background: white;
        border: 1px solid rgba(255,255,255,.95);
        border-radius: 5px;
        box-shadow: 0 2px 8px rgba(0,0,0,.25), 0 0 0 4px rgba(255,255,255,.18);
    }
    .scale-labels {
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
        font-size: 11px;
        opacity: .58;
    }
    .scale-description {
        margin-top: 18px;
        font-size: 11px;
        line-height: 1.55;
        opacity: .58;
    }
    .history-analysis-title {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #172033;
        font-size: 15px;
        font-weight: 800;
        line-height: 1.4;
    }
    .history-status-dot {
        width: 9px;
        height: 9px;
        flex: 0 0 9px;
        border-radius: 50%;
        box-shadow: 0 0 0 4px rgba(148,163,184,.10);
    }
    .history-status-dot.green { background: #22c55e; }
    .history-status-dot.orange { background: #f59e0b; }
    .history-status-dot.red { background: #ef4444; }
    .ingredient-row {
        position: relative;
        display: grid;
        grid-template-columns: 12px minmax(190px, .85fr) minmax(0, 1.6fr);
        gap: 20px;
        align-items: center;
        overflow: hidden;
        margin: 10px 0;
        padding: 19px 22px;
        border: 1px solid rgba(255,255,255,.82);
        border-radius: 20px;
        background: linear-gradient(135deg, rgba(255,255,255,.66), rgba(255,255,255,.38));
        box-shadow: 0 10px 28px rgba(30,64,175,.06), inset 0 1px 0 rgba(255,255,255,.9);
        backdrop-filter: blur(16px) saturate(135%);
        -webkit-backdrop-filter: blur(16px) saturate(135%);
    }
    .ingredient-row::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 5px;
        background: var(--ingredient-color, #f59e0b);
    }
    .ingredient-status {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--ingredient-color, #f59e0b);
        box-shadow: 0 0 0 5px color-mix(in srgb, var(--ingredient-color, #f59e0b) 14%, transparent);
    }
    .ingredient-name {
        color: #172033;
        font-size: 16px;
        font-weight: 850;
        line-height: 1.35;
    }
    .ingredient-type {
        margin-top: 4px;
        color: #5d7490;
        font-size: 12px;
        font-weight: 750;
        letter-spacing: .02em;
    }
    .ingredient-explanation {
        color: #394963;
        font-size: 14px;
        line-height: 1.58;
    }
    .input-intro {
        margin: -2px 0 18px;
        color: #61738d;
        font-size: 13px;
        line-height: 1.55;
    }
    .result-hero {
        display: grid;
        grid-template-columns: 190px 1fr;
        gap: 28px;
        align-items: center;
        position: relative;
        overflow: hidden;
        margin: 14px 0 24px;
        padding: 28px 32px;
        border: 1px solid rgba(255,255,255,.88);
        border-radius: 28px;
        background:
            radial-gradient(circle at 93% 16%, rgba(24,200,255,.25), transparent 30%),
            radial-gradient(circle at 6% 100%, rgba(22,119,255,.16), transparent 36%),
            linear-gradient(135deg, rgba(255,255,255,.78), rgba(255,255,255,.43));
        box-shadow: 0 22px 60px rgba(30,64,175,.11), inset 0 1px 0 rgba(255,255,255,.95);
        backdrop-filter: blur(24px) saturate(150%);
        -webkit-backdrop-filter: blur(24px) saturate(150%);
        animation: ev-fade-up .45s ease both;
    }
    .result-score {
        display: grid;
        place-items: center;
        width: 158px;
        height: 158px;
        border-radius: 50%;
        border: 1px solid rgba(255,255,255,.95);
        background: rgba(255,255,255,.50);
        box-shadow: 0 14px 34px rgba(22,119,255,.12), inset 0 1px 0 rgba(255,255,255,.95);
    }
    .result-score-value {
        color: #10203c;
        font-size: 54px;
        font-weight: 850;
        letter-spacing: -3px;
        line-height: .9;
        text-align: center;
    }
    .result-score-value span {
        display: block;
        margin-top: 8px;
        color: #60738e;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 1.4px;
    }
    .result-kicker {
        color: #1677ff;
        font-size: 11px;
        font-weight: 850;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    .result-title {
        margin: 6px 0 8px;
        color: #0b1220;
        font-size: clamp(22px, 2.5vw, 31px);
        font-weight: 850;
        letter-spacing: -1px;
        line-height: 1.15;
    }
    .result-summary { color: #566b86; font-size: 14px; line-height: 1.6; }
    .result-meter { height: 8px; margin: 16px 0 13px; overflow: hidden; border-radius: 999px; background: rgba(148,163,184,.16); }
    .result-meter > span { display: block; width: var(--score); height: 100%; border-radius: inherit; background: linear-gradient(90deg, #1677ff, #18c8ff); box-shadow: 0 0 16px rgba(24,200,255,.4); animation: ev-score-fill .9s ease both; transform-origin: left; }
    .result-facts { display: flex; flex-wrap: wrap; gap: 8px; }
    .result-fact { padding: 7px 10px; border: 1px solid rgba(255,255,255,.78); border-radius: 999px; background: rgba(255,255,255,.45); color: #4b627f; font-size: 12px; font-weight: 750; }
    .allergy-card, .allergy-clear, .ai-recommendation {
        position: relative;
        overflow: hidden;
        margin: 10px 0;
        padding: 22px 24px;
        border: 1px solid rgba(255,255,255,.84);
        border-radius: 22px;
        background: rgba(255,255,255,.48);
        box-shadow: 0 12px 32px rgba(30,64,175,.06), inset 0 1px 0 rgba(255,255,255,.92);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
    }
    .allergy-card { border-left: 5px solid #f59e0b; }
    .allergy-card.high { border-left-color: #ef4444; }
    .allergy-card.low { border-left-color: #18a86b; }
    .allergy-label { color: #b56e00; font-size: 11px; font-weight: 850; letter-spacing: 1.5px; text-transform: uppercase; }
    .allergy-card.high .allergy-label { color: #d83737; }
    .allergy-card.low .allergy-label { color: #188756; }
    .allergy-name { margin: 5px 0 7px; color: #142038; font-size: 21px; font-weight: 850; line-height: 1.28; }
    .allergy-text, .recommendation-text { color: #40536c; font-size: 14px; line-height: 1.62; }
    .allergy-clear { border-left: 5px solid #22c55e; color: #176a46; font-weight: 750; }
    .ai-recommendation { border-left: 5px solid #1677ff; background: linear-gradient(100deg, rgba(255,255,255,.68), rgba(224,249,255,.62)); }
    .ai-recommendation-title { color: #1162d1; font-size: 12px; font-weight: 850; letter-spacing: 1.8px; text-transform: uppercase; }
    .insight-list { margin: 8px 0 0; padding-left: 19px; color: #34455e; font-size: 14px; line-height: 1.65; }
    .insight-card { height: 100%; padding: 18px 20px; border: 1px solid rgba(255,255,255,.82); border-radius: 20px; background: rgba(255,255,255,.42); box-shadow: inset 0 1px 0 rgba(255,255,255,.9); }
    .insight-card-title { color: #172033; font-size: 16px; font-weight: 850; }
    @keyframes ev-fade-up { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes ev-score-fill { from { transform: scaleX(0); } to { transform: scaleX(1); } }
    .stButton > button {
        border-radius: 16px !important;
        border: 1px solid rgba(255,255,255,.85) !important;
        background: linear-gradient(135deg, rgba(255,255,255,.78), rgba(255,255,255,.46)) !important;
        color: #1455ad !important;
        box-shadow: 0 10px 28px rgba(30,64,175,.08), inset 0 1px 0 rgba(255,255,255,.95);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        transition: transform .18s ease, box-shadow .18s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 14px 32px rgba(30,64,175,.13), inset 0 1px 0 rgba(255,255,255,1);
    }
    .stButton > button[kind="primary"] {
        color: white !important;
        border-color: rgba(255,255,255,.42) !important;
        background: linear-gradient(135deg, #1677ff, #12bde9) !important;
        box-shadow: 0 12px 30px rgba(22,119,255,.25), inset 0 1px 0 rgba(255,255,255,.35);
    }
    div[data-baseweb="input"],
    div[data-baseweb="textarea"],
    div[data-baseweb="select"],
    [data-testid="stFileUploaderDropzone"] {
        border-radius: 18px !important;
    }
    div[data-baseweb="input"] > div,
    div[data-baseweb="textarea"] > div,
    div[data-baseweb="select"] > div,
    [data-testid="stFileUploaderDropzone"] {
        background: rgba(255,255,255,.52) !important;
        border-color: rgba(255,255,255,.82) !important;
        box-shadow: inset 0 1px 0 rgba(255,255,255,.8);
        backdrop-filter: blur(12px);
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: rgba(22,119,255,.30) !important;
        box-shadow: 0 10px 30px rgba(22,119,255,.08);
    }
    @media (max-width: 760px) {
        .block-container { padding-top: 2rem; padding-left: .8rem; padding-right: .8rem; }
        .ev-hero,
        .st-key-ev-input-panel,
        .st-key-ev-process-panel { padding: 22px !important; border-radius: 23px !important; }
        .workflow { gap: 6px; }
        .workflow-arrow { display: none; }
        .workflow-step { font-size: 11px; padding: 8px 10px; }
        .score-number { font-size: 48px; }
        .ingredient-row { grid-template-columns: 12px 1fr; gap: 13px; padding: 17px; }
        .ingredient-explanation { grid-column: 2; }
        .result-hero { grid-template-columns: 1fr; gap: 19px; padding: 22px; }
        .result-score { width: 126px; height: 126px; }
        .result-score-value { font-size: 44px; }
        .result-facts { gap: 6px; }
        .result-fact { font-size: 11px; }
        .allergy-card, .allergy-clear, .ai-recommendation { padding: 18px; border-radius: 18px; }
        .allergy-name { font-size: 18px; }
    }
    @media (prefers-reduced-motion: reduce) {
        .ev-analysis::before, .ev-progress > div,
        .result-hero, .result-meter > span { animation: none; }
    }
</style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# GEMINI
# ============================================================
MODEL_NAME = "gemini-3.5-flash-lite"
def gemini_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
def gemini_text_request(prompt):
    client = gemini_client()
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    return response.text or ""
def gemini_image_request(image_bytes, mime_type, prompt):
    client = gemini_client()
    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type,
    )
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[image_part, prompt],
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    return response.text or ""
# ============================================================
# ANALYSIS PROMPT
# ============================================================
ANALYSIS_RULES = """
Ты — интеллектуальный анализатор состава потребительских продуктов
E-vision.
Твоя задача — анализировать состав продукта информативно, аккуратно
и без выдумывания данных.
ВАЖНЫЕ ПРАВИЛА:
1. Анализируй только информацию, которую реально получил.
2. Никогда не придумывай ингредиенты, концентрации, проценты, свойства
   или информацию, которой нет во входных данных.
3. Учитывай назначение продукта и контекст его категории.
4. Не считай сложное химическое название автоматически вредным.
5. Не считай синтетический компонент автоматически плохим.
6. Учитывай функцию каждого компонента.
7. Если порядок ингредиентов имеет значение для категории, учитывай его.
8. Если состав неполный или часть фотографии нечитаема,
   composition_complete должен быть false.
9. При неполной информации снижай confidence.
10. Не ставь медицинские диагнозы.
11. Не обещай лечение.
12. Не утверждай абсолютную безопасность.
13. Не утверждай гарантированный вред.
14. Для фармацевтических и медицинских продуктов давай только
    информационную оценку состава и не давай назначений по лечению.
15. Для аллергенов говори только о потенциально значимых компонентах.
    Не утверждай, что у человека обязательно будет аллергическая реакция.
16. Не используй red только потому, что название вещества выглядит
    «химическим».
17. Объяснения должны быть понятными обычному пользователю.
КАТЕГОРИИ:
- Еда
- Напитки
- Косметика
- Средства личной гигиены
- Бытовая химия
- Чистящие средства
- Товары для животных
- Фармацевтические / медицинские продукты
- Другое
После категории обязательно указывай конкретный тип продукта.
Например:
Категория: Косметика
Тип: Очищающая пенка для лица
Категория: Еда
Тип: Шоколадный батончик
Категория: Напитки
Тип: Газированный напиток
Категория: Бытовая химия
Тип: Средство для мытья посуды
Не используй название категории как product_type.
ОЦЕНКА ПО КАТЕГОРИЯМ:
Для еды учитывай:
- добавленные сахара;
- соль;
- насыщенные жиры;
- белок;
- клетчатку;
- степень переработки;
- характер добавок.
Для напитков учитывай:
- сахар;
- подсластители;
- кофеин;
- кислотность;
- основные компоненты.
Для косметики учитывай:
- ПАВ;
- увлажнители;
- кондиционирующие компоненты;
- консерванты;
- отдушки;
- потенциально раздражающие компоненты;
- функциональность формулы.
Для средств личной гигиены учитывай:
- очищающие компоненты;
- ПАВ;
- увлажняющие и кондиционирующие компоненты;
- консерванты;
- отдушки;
- потенциально раздражающие компоненты;
- назначение средства.
Для бытовой химии и чистящих средств учитывай:
- ПАВ;
- растворители;
- отдушки;
- консерванты;
- потенциально раздражающие компоненты;
- назначение продукта.
Для товаров для животных учитывай:
- основные питательные компоненты;
- наполнители;
- консерванты;
- соответствие назначению.
ИНДЕКС СОСТАВА:
0–39 — требуется осторожность
40–69 — средний
70–84 — хороший
85–100 — очень благоприятный
Индекс является информационной оценкой благоприятности состава
с учётом назначения продукта. Это НЕ показатель абсолютной безопасности
и НЕ медицинский показатель.
VERDICT:
green — в целом благоприятный состав
orange — есть особенности, требующие внимания
red — есть существенные основания для осторожности
СТАТУС ИНГРЕДИЕНТА:
green — обычный функциональный компонент
orange — может требовать внимания в зависимости от продукта
и индивидуальной переносимости
red — существенные основания для осторожности
Не ставь red только из-за сложного названия вещества.
Если компонент не требует отдельного внимания, обязательно возвращай `attention_reason: null`, а не строку `None`, `null`, `нет` или пустое текстовое значение.
ALLERGY_ALERTS:
Выделяй потенциально значимые аллергены или компоненты,
которые могут иметь значение при индивидуальной чувствительности.
Не утверждай наличие аллергии у конкретного человека.
ФОРМАТ:
Верни только валидный JSON со следующими полями:
{
  "score": 0,
  "verdict": "green",
  "verdict_text": "Краткий вывод",
  "category": "Косметика",
  "product_type": "Конкретный тип продукта",
  "confidence": "high",
  "composition_complete": true,
  "composition_text": "Распознанный или предоставленный состав",
  "summary": "Понятное подробное описание состава",
  "ingredients": [
    {
      "name": "Название ингредиента",
      "type": "Назначение",
      "status": "green",
      "explanation": "Что делает компонент и зачем он нужен",
      "attention_reason": null
    }
  ],
  "benefits": [
    "Положительная сторона"
  ],
  "risks": [
    "Что требует внимания"
  ],
  "allergy_alerts": [
    {
      "name": "Компонент",
      "reason": "Почему он может быть значим при индивидуальной чувствительности",
      "level": "attention"
    }
  ],
  "allergy_note": "Общая осторожная заметка",
  "recommendation": "Итоговая рекомендация"
}
Ограничения JSON:
- score — только целое число от 0 до 100;
- verdict — только green, orange или red;
- confidence — только high, medium или low;
- status — только green, orange или red;
- allergy level — high, attention или low;
- не добавляй Markdown;
- не добавляй комментарии вне JSON;
- не добавляй выдуманные ингредиенты.
"""
# ============================================================
# HELPERS
# ============================================================
def clean_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
def as_list(value):
    return value if isinstance(value, list) else []
def safe_score(value):
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 50
def verdict_icon(verdict):
    return {
        "green": ":material/check_circle:",
        "orange": ":material/radio_button_checked:",
        "red": ":material/cancel:",
    }.get(str(verdict).lower(), ":material/radio_button_checked:")
def confidence_label(value):
    return {
        "high": "Высокая",
        "medium": "Средняя",
        "low": "Низкая",
    }.get(str(value).lower(), "Средняя")
def normalize_result(data):
    if not isinstance(data, dict):
        raise ValueError("Gemini вернул неправильный формат JSON.")
    result = dict(data)
    result["score"] = safe_score(result.get("score"))
    result["verdict"] = str(result.get("verdict", "orange")).lower()
    if result["verdict"] not in {"green", "orange", "red"}:
        result["verdict"] = "orange"
    result["confidence"] = str(
        result.get("confidence", "medium")
    ).lower()
    if result["confidence"] not in {"high", "medium", "low"}:
        result["confidence"] = "medium"
    result["ingredients"] = as_list(result.get("ingredients", []))
    result["benefits"] = as_list(result.get("benefits", []))
    result["risks"] = as_list(result.get("risks", []))
    result["allergy_alerts"] = as_list(
        result.get("allergy_alerts", [])
    )
    result["composition_complete"] = bool(
        result.get("composition_complete", True)
    )
    return result
# ============================================================
# HISTORY
# ============================================================
HISTORY_FILE = "history.json"
def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            history = json.load(file)
        return history if isinstance(history, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []
def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(
            history,
            file,
            ensure_ascii=False,
            indent=2,
        )
def add_to_history(product_text, result):
    history = load_history()
    item = {
        "id": hashlib.md5(
            f"{product_text}|{datetime.now().isoformat()}".encode("utf-8")
        ).hexdigest(),
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "text": product_text,
        "result": result,
    }
    history.insert(0, item)
    save_history(history[:50])
def delete_from_history(item_id):
    history = load_history()
    history = [
        item
        for item in history
        if item.get("id") != item_id
    ]
    save_history(history)
# ============================================================
# TEXT ANALYSIS
# ============================================================
def analyze_text_product(text):
    prompt = f"""
{ANALYSIS_RULES}
ИСТОЧНИК ДАННЫХ: ТЕКСТ.
Проанализируй следующий предоставленный пользователем состав:
--- НАЧАЛО СОСТАВА ---
{text}
--- КОНЕЦ СОСТАВА ---
Не добавляй сведения, которых нет в составе.
Если состав выглядит неполным, укажи composition_complete=false.
Верни только JSON.
"""
    answer = gemini_text_request(prompt)
    data = json.loads(clean_json(answer))
    return normalize_result(data)
# ============================================================
# PHOTO ANALYSIS — GEMINI VISION
# ============================================================
def analyze_photo_product(image_bytes, mime_type):
    prompt = f"""
{ANALYSIS_RULES}
ИСТОЧНИК ДАННЫХ: ФОТОГРАФИЯ ЭТИКЕТКИ.
Сначала внимательно прочитай текст на фотографии.
Затем используй только действительно читаемую информацию
с фотографии для анализа.
КРИТИЧЕСКИ ВАЖНО:
1. Не придумывай отсутствующие ингредиенты.
2. Не восстанавливай нечитаемые слова по догадке.
3. Если часть состава размыта, закрыта, слишком мелкая
   или обрезана, отметь это.
4. composition_complete=false, если состав невозможно
   прочитать полностью или уверенно определить.
5. composition_text должен содержать только текст состава,
   который реально удалось прочитать с фотографии.
6. Сохраняй порядок ингредиентов.
7. Не подменяй нечитаемый текст похожим веществом.
8. Если на фотографии видна дополнительная информация,
   используй её только если она действительно читаема.
9. Анализируй именно тот продукт, который виден на фото.
Верни только JSON.
"""
    answer = gemini_image_request(
        image_bytes,
        mime_type,
        prompt,
    )
    data = json.loads(clean_json(answer))
    return normalize_result(data)
# ============================================================
# RENDER HISTORY RESULT
# ============================================================
def render_analysis_result(
    result,
    source_text,
    saved_date=None,
    show_close=False,
):
    score = safe_score(result.get("score"))
    verdict = str(
        result.get("verdict", "orange")
    ).lower()
    if verdict not in {"green", "orange", "red"}:
        verdict = "orange"
    icon = verdict_icon(verdict)
    category = str(
        result.get("category", "Не определено")
    )
    product_type = str(
        result.get("product_type", "Не определено")
    )
    if product_type.strip().lower() == category.strip().lower():
        product_type = "Не удалось точно определить"
    confidence = confidence_label(
        result.get("confidence", "medium")
    )
    st.divider()
    st.subheader(":material/analytics: Результат анализа")
    if saved_date:
        st.caption(f"Дата анализа: {saved_date}")
    verdict_text = str(
        result.get("verdict_text", "Состав требует внимания")
    )
    summary = str(result.get("summary", "Описание отсутствует."))
    allergy_alerts = as_list(result.get("allergy_alerts", []))
    risks = as_list(result.get("risks", []))
    verdict_label = {
        "green": "Благоприятный состав",
        "orange": "Есть особенности",
        "red": "Требуется осторожность",
    }.get(verdict, "Есть особенности")
    allergy_fact = (
        "Аллергены: есть особенности"
        if allergy_alerts
        else "Аллергены: не выделены"
    )
    risk_fact = (
        f"Риски: {len(risks)}"
        if risks
        else "Риски: не выделены"
    )
    completeness_fact = (
        "Состав: полный"
        if result.get("composition_complete", True)
        else "Состав: частично прочитан"
    )
    st.markdown(
        f'<div class="result-hero">'
        f'<div class="result-score"><div class="result-score-value">{score}'
        f'<span>SAFETY SCORE / 100</span></div></div>'
        f'<div><div class="result-kicker">E-VISION · ANALYSIS COMPLETE</div>'
        f'<div class="result-title">{html.escape(verdict_label)}</div>'
        f'<div class="result-summary">{html.escape(verdict_text)} · '
        f'{html.escape(category)}: {html.escape(product_type)}</div>'
        f'<div class="result-meter" style="--score:{score}%;"><span></span></div>'
        f'<div class="result-facts">'
        f'<span class="result-fact">{html.escape(allergy_fact)}</span>'
        f'<span class="result-fact">{html.escape(risk_fact)}</span>'
        f'<span class="result-fact">{html.escape(completeness_fact)}</span>'
        f'<span class="result-fact">Уверенность: {html.escape(confidence)}</span>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )
    st.caption(summary)
    if not result.get("composition_complete", True):
        st.warning(
            ":material/warning: Состав может быть неполным или часть информации "
            "на фотографии/в исходных данных могла быть нечитаемой. "
            "Индекс и вывод могут быть менее точными."
        )
    composition_text = str(
        result.get("composition_text", "")
    ).strip()
    if composition_text:
        with st.expander(":material/description: Состав, использованный для анализа"):
            st.code(
                composition_text,
                language=None,
            )
    # ========================================================
    # INGREDIENTS
    # ========================================================
    st.subheader(":material/biotech: Разбор компонентов")
    ingredients = as_list(
        result.get("ingredients", [])
    )
    if ingredients:
        for ingredient in ingredients:
            if not isinstance(ingredient, dict):
                continue
            name = str(
                ingredient.get(
                    "name",
                    "Ингредиент",
                )
            )
            ingredient_type = str(
                ingredient.get(
                    "type",
                    "Назначение не указано",
                )
            )
            status = str(
                ingredient.get(
                    "status",
                    "orange",
                )
            ).lower()
            color = {
                "green": "#22c55e",
                "orange": "#f59e0b",
                "red": "#ef4444",
            }.get(status, "#f59e0b")
            explanation = str(
                ingredient.get(
                    "explanation",
                    "",
                )
            ).strip()
            st.markdown(
                f'<div class="ingredient-row" style="--ingredient-color: {color};">'
                f'<span class="ingredient-status"></span>'
                f'<div><div class="ingredient-name">{html.escape(name)}</div>'
                f'<div class="ingredient-type">{html.escape(ingredient_type)}</div></div>'
                f'<div class="ingredient-explanation">{html.escape(explanation)}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            raw_attention_reason = ingredient.get(
                "attention_reason"
            )
            attention_reason = (
                str(raw_attention_reason).strip()
                if raw_attention_reason is not None
                else ""
            )
            ignored_attention_values = {
                "",
                "none",
                "null",
                "нет",
                "не выявлено",
            }
            if attention_reason.lower() not in ignored_attention_values:
                st.warning(
                    f":material/warning: {attention_reason}"
                )
    else:
        st.info(
            "Подробный разбор компонентов не получен."
        )
    # ========================================================
    # ALLERGY ALERTS
    # ========================================================
    allergy_note = str(
        result.get("allergy_note", "")
    ).strip()
    st.subheader(
        ":material/warning: Аллергены и чувствительность"
    )
    if allergy_alerts:
        for alert in allergy_alerts:
            if not isinstance(alert, dict):
                continue
            alert_name = str(
                alert.get(
                    "name",
                    "Компонент",
                )
            )
            alert_reason = str(
                alert.get(
                    "reason",
                    "Может требовать внимания "
                    "при индивидуальной чувствительности.",
                )
            )
            alert_level = str(
                alert.get(
                    "level",
                    "attention",
                )
            ).lower()
            alert_title = {
                "high": "Требует особого внимания",
                "low": "Невысокий уровень внимания",
            }.get(alert_level, "Требует внимания")
            alert_class = (
                alert_level
                if alert_level in {"high", "low"}
                else "attention"
            )
            st.markdown(
                f'<div class="allergy-card {alert_class}">'
                f'<div class="allergy-label">{html.escape(alert_title)}</div>'
                f'<div class="allergy-name">{html.escape(alert_name)}</div>'
                f'<div class="allergy-text">{html.escape(alert_reason)}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="allergy-clear">✓ Потенциальные аллергены не '
            'обнаружены в распознанном составе.</div>',
            unsafe_allow_html=True,
        )
    if allergy_note:
        st.caption(
            f" {allergy_note}"
        )
    # ========================================================
    # FINAL INFORMATION
    # ========================================================
    st.subheader(":material/fact_check: Итог")
    benefits = as_list(
        result.get("benefits", [])
    )
    recommendation = str(
        result.get("recommendation", "Рекомендация отсутствует.")
    )
    st.markdown(
        f'<div class="ai-recommendation">'
        f'<div class="ai-recommendation-title">E-VISION · AI-РЕКОМЕНДАЦИЯ</div>'
        f'<div class="allergy-name">Итог для вас</div>'
        f'<div class="recommendation-text">{html.escape(recommendation)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    benefits_col, risks_col = st.columns(2, gap="medium")
    benefits_html = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in benefits
    ) or "<li>Существенных положительных сторон не выделено.</li>"
    risks_html = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in risks
    ) or "<li>Существенных замечаний не выделено.</li>"
    with benefits_col:
        st.markdown(
            '<div class="insight-card"><div class="insight-card-title">'
            '✓ Положительные стороны</div><ul class="insight-list">'
            f"{benefits_html}</ul></div>",
            unsafe_allow_html=True,
        )
    with risks_col:
        st.markdown(
            '<div class="insight-card"><div class="insight-card-title">'
            '⚠ Что требует внимания</div><ul class="insight-list">'
            f"{risks_html}</ul></div>",
            unsafe_allow_html=True,
        )
    st.divider()
    st.caption(
        ":material/info: Индекс состава является информационной оценкой "
        "благоприятности состава с учётом назначения продукта. "
        "Он не гарантирует абсолютную безопасность и не является "
        "медицинской рекомендацией."
    )
    if show_close:
        if st.button(":material/close: Закрыть сохранённый анализ"):
            st.session_state.pop(
                "selected_history",
                None,
            )
            st.rerun()
# ============================================================
# HEADER
# ============================================================
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""
logo_base64 = get_base64_image("logo.png")
if logo_base64:
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="height: 64px; width: 64px; margin-right: 12px; vertical-align: middle; border-radius: 14px; box-shadow: 0 8px 24px rgba(30,64,175,.12);">'
else:
    logo_html = '<span class="brand-mark">E</span>'
st.markdown(
    f"""
    <div class="main-title" style="display: flex; align-items: center; margin-bottom: 15px;">
        {logo_html}
        <div>
            Анализатор состава продуктов <span class="brand-name">E-vision</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtitle">'
    "Проверьте состав продукта и получите понятный "
    "анализ с рекомендациями."
    "</div>",
    unsafe_allow_html=True,
)
st.markdown(
    """<div class="ev-hero">
<div class="ev-kicker">E-VISION · AI PRODUCT ANALYSIS</div>
<div class="ev-hero-title">Понимайте состав продукта с первого взгляда.</div>
<div class="ev-hero-text">
Загрузите фотографию этикетки или вставьте состав вручную.
E-vision распознает компоненты, объяснит их назначение и
сформирует понятный индекс состава.
</div>
<div class="workflow">
<span class="workflow-step"><b>01</b> Фото</span>
<span class="workflow-arrow">→</span>
<span class="workflow-step"><b>02</b> Vision AI</span>
<span class="workflow-arrow">→</span>
<span class="workflow-step"><b>03</b> Ингредиенты</span>
<span class="workflow-arrow">→</span>
<span class="workflow-step"><b>04</b> Анализ</span>
<span class="workflow-arrow">→</span>
<span class="workflow-step"><b>05</b> Результат</span>
</div>
</div>""",
    unsafe_allow_html=True,
)
# ============================================================
# SIDEBAR — HISTORY
# ============================================================
with st.sidebar:
    st.header(":material/history: История анализов")
    history = load_history()
    if not history:
        st.caption("Здесь появятся ваши анализы.")
    else:
        st.caption(
            f"Сохранено анализов: {len(history)}"
        )
        if st.button(
            ":material/delete_sweep: Очистить всю историю",
            use_container_width=True,
        ):
            save_history([])
            st.session_state.pop(
                "selected_history",
                None,
            )
            st.rerun()
        st.divider()
        for item in history:
            saved_result = item.get(
                "result",
                {},
            )
            score = safe_score(
                saved_result.get("score")
            )
            verdict = str(
                saved_result.get(
                    "verdict",
                    "orange",
                )
            ).lower()
            if verdict not in {"green", "orange", "red"}:
                verdict = "orange"
            product_type = saved_result.get(
                "product_type",
                "Неизвестный продукт",
            )
            category = saved_result.get(
                "category",
                "Другое",
            )
            st.markdown(
                f'<div class="history-analysis-title">'
                f'<span class="history-status-dot {verdict}"></span>'
                f'<span>{html.escape(str(product_type))}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
            st.caption(
                f"{category} · {score}/100"
            )
            st.caption(
                item.get("date", "")
            )
            col_open, col_delete = st.columns(
                [3, 1]
            )
            with col_open:
                if st.button(
                    "Открыть",
                    key=f"open_{item['id']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_history = item
                    st.rerun()
            with col_delete:
                if st.button(
                    ":material/delete: ",
                    key=f"delete_{item['id']}",
                    use_container_width=True,
                ):
                    delete_from_history(
                        item["id"]
                    )
                    if (
                        st.session_state.get(
                            "selected_history",
                            {},
                        ).get("id")
                        == item["id"]
                    ):
                        st.session_state.pop(
                            "selected_history",
                            None,
                        )
                    st.rerun()
            st.divider()
# ============================================================
# SELECTED HISTORY ANALYSIS
# ============================================================
selected_history = st.session_state.get(
    "selected_history"
)
if selected_history:
    saved_result = selected_history.get(
        "result",
        {},
    )
    st.subheader(":material/history: Сохранённый анализ")
    render_analysis_result(
        saved_result,
        selected_history.get("text", ""),
        saved_date=selected_history.get("date", ""),
        show_close=True,
    )
# ============================================================
# INPUT
# ============================================================
input_col, info_col = st.columns(
    [1, 1],
    gap="large",
)
# ============================================================
# INPUT COLUMN
# ============================================================
with input_col:
    with st.container(border=True, key="ev-input-panel"):
        st.markdown(
            '<div class="section-kicker">01 · INPUT</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="glass-section-title">
                <span class="glass-section-number">01</span>
                <span class="glass-section-name">Анализ продукта</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="input-intro">Загрузите фото этикетки или вставьте '
            'состав вручную — E-vision использует AI, чтобы объяснить '
            'ингредиенты и оценить состав.</div>',
            unsafe_allow_html=True,
        )
        method = st.radio(
            "Способ ввода",
            [
                ":material/edit_note: Ввести вручную",
                ":material/photo_camera: Загрузить фото",
            ],
            horizontal=True,
            label_visibility="collapsed",
        )
        product_text = ""
        uploaded_image_bytes = None
        uploaded_mime_type = None
        if method == ":material/edit_note: Ввести вручную":
            product_text = st.text_area(
                "Состав",
                placeholder=(
                    "Введите состав продукта...\n\n"
                    "Например: вода, сахар, какао-порошок..."
                ),
                height=220,
            )
        else:
            uploaded = st.file_uploader(
                "Фотография состава",
                type=[
                    "jpg",
                    "jpeg",
                    "png",
                    "webp",
                ],
                help=(
                    "Лучше фотографировать этикетку прямо, "
                    "близко и при хорошем освещении."
                ),
            )
            if uploaded:
                image_bytes = uploaded.getvalue()
                image_hash = hashlib.md5(
                    image_bytes
                ).hexdigest()
                try:
                    image = ImageOps.exif_transpose(
                        Image.open(
                            BytesIO(image_bytes)
                        )
                    ).convert("RGB")
                    st.image(
                        image,
                        caption="Загруженная фотография",
                        use_container_width=True,
                    )
                    uploaded_image_bytes = image_bytes
                    uploaded_mime_type = (
                        uploaded.type
                        or "image/jpeg"
                    )
                    st.success(
                        ":material/check_circle: Фото готово. Gemini будет читать "
                        "состав непосредственно с изображения."
                    )
                    st.session_state.image_hash = image_hash
                except Exception as error:
                    st.error(
                        f"Не удалось открыть изображение: {error}"
                    )
        analyze = st.button(
            ":material/search: Анализировать состав",
            type="primary",
            use_container_width=True,
        )
# ============================================================
# HOW IT WORKS
# ============================================================
with info_col:
    with st.container(border=True, key="ev-process-panel"):
        st.markdown(
            '<div class="section-kicker">02 · PROCESS</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="glass-section-title">
                <span class="glass-section-number">02</span>
                <span class="glass-section-name">Как работает E-vision</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if method == ":material/photo_camera: Загрузить фото":
            steps = [
                (
                    "01",
                    "Получаем фотографию",
                    "Вы загружаете фото этикетки продукта.",
                ),
                (
                    "02",
                    "Читаем изображение",
                    "Gemini Vision непосредственно читает текст на фотографии.",
                ),
                (
                    "03",
                    "Проверяем читаемость",
                    "ИИ отмечает нечитаемые или отсутствующие участки.",
                ),
                (
                    "04",
                    "Определяем продукт",
                    "Определяются категория и конкретный тип.",
                ),
                (
                    "05",
                    "Анализируем состав",
                    "Компоненты оцениваются с учётом назначения продукта.",
                ),
            ]
        else:
            steps = [
                (
                    "01",
                    "Получаем состав",
                    "Вы вводите состав продукта вручную.",
                ),
                (
                    "02",
                    "Определяем продукт",
                    "Определяются категория и конкретный тип.",
                ),
                (
                    "03",
                    "Анализируем состав",
                    "Компоненты оцениваются с учётом назначения продукта.",
                ),
                (
                    "04",
                    "Ищем особенности",
                    "ИИ выделяет потенциально важные компоненты.",
                ),
                (
                    "05",
                    "Формируем вывод",
                    "Вы получаете индекс, объяснение и рекомендации.",
                ),
            ]
        for number, title, description in steps:
            st.markdown(
                f"""
                <div class="process-step">
                    <div class="process-number">{number}</div>
                    <div>
                        <div class="process-title">{title}</div>
                        <div class="process-description">{description}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
# ============================================================
# ANALYSIS
# ============================================================
if analyze:
    # --------------------------------------------------------
    # PHOTO
    # --------------------------------------------------------
    if method == ":material/photo_camera: Загрузить фото":
        if not uploaded_image_bytes:
            st.warning(
                ":material/warning: Сначала загрузите фотографию состава."
            )
            st.stop()
        st.markdown(
            """
            <div class="ev-analysis">
                <div class="ev-analysis-label">VISION AI · ANALYZING</div>
                <div class="ev-analysis-title">Сканируем этикетку и разбираем состав...</div>
                <div class="ev-progress"><div></div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.spinner(
            ":material/auto_awesome: Gemini читает фотографию и анализирует состав..."
        ):
            try:
                result = analyze_photo_product(
                    uploaded_image_bytes,
                    uploaded_mime_type,
                )
            except Exception as error:
                st.error(
                    f"Ошибка анализа фотографии: {error}"
                )
                st.stop()
        composition_text = str(
            result.get(
                "composition_text",
                "",
            )
        ).strip()
        history_text = (
            composition_text
            if composition_text
            else "[Анализ выполнен непосредственно по фотографии]"
        )
    # --------------------------------------------------------
    # MANUAL TEXT
    # --------------------------------------------------------
    else:
        if not product_text.strip():
            st.warning(
                ":material/warning: Введите состав продукта."
            )
            st.stop()
        st.markdown(
            """
            <div class="ev-analysis">
                <div class="ev-analysis-label">E-VISION · ANALYZING</div>
                <div class="ev-analysis-title">Разбираем ингредиенты и формируем оценку...</div>
                <div class="ev-progress"><div></div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.spinner(
            ":material/auto_awesome: Анализируем состав..."
        ):
            try:
                result = analyze_text_product(
                    product_text
                )
            except Exception as error:
                st.error(
                    f"Ошибка анализа Gemini: {error}"
                )
                st.stop()
        history_text = product_text
    # --------------------------------------------------------
    # SAVE + DISPLAY
    # --------------------------------------------------------
    add_to_history(
        history_text,
        result,
    )
    render_analysis_result(
        result,
        history_text,
    )

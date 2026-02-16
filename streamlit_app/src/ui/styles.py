import streamlit as st

# Hierarchy types (4 levels: Goal → Objective → Key Result → Task)
# Note: Strategy and Initiative are now TAGS, not navigable levels
TYPES = ["GOAL", "OBJECTIVE", "KEY_RESULT", "TASK"]

CHILD_TYPE_MAP = {
    "GOAL": "OBJECTIVE",
    "OBJECTIVE": "KEY_RESULT",
    "KEY_RESULT": "TASK",
    "TASK": None 
}

TYPE_ICONS = {
    "GOAL": "🏁",
    "STRATEGY": "♟️",
    "OBJECTIVE": "🎯",
    "KEY_RESULT": "📊",
    "INITIATIVE": "⚡",
    "TASK": "📋"
}

# Colors for mind map visualization
TYPE_COLORS = {
    "GOAL": "#E53935",       # Red
    "STRATEGY": "#1E88E5",   # Blue
    "OBJECTIVE": "#43A047",  # Green
    "KEY_RESULT": "#FB8C00", # Orange
    "INITIATIVE": "#8E24AA", # Purple
    "TASK": "#757575"        # Gray
}

# Size by hierarchy depth (larger for higher-level nodes)
TYPE_SIZES = {
    "GOAL": 35,
    "STRATEGY": 30,
    "OBJECTIVE": 25,
    "KEY_RESULT": 22,
    "INITIATIVE": 18,
    "TASK": 15
}


def inject_dialog_styles():
    """
    CSS to prevent dialog from closing on backdrop click (by hiding the close button backdrop) 
    and styling elements inside.
    """
    st.markdown(
        """
        <style>
            /* This is a hacky way to prevent backdrop clicks in Streamlit 1.34+ */
            [data-testid="stDialog"] [data-testid="stBaseButton-secondary"] {
                /* We can't easily prevent the click, but we can make the dialog more 'modal' */
            }
            
            /* Custom Scrollbar for white-themed dialogs */
            [data-testid="stDialog"] ::-webkit-scrollbar {
                width: 8px;
            }
            [data-testid="stDialog"] ::-webkit-scrollbar-thumb {
                background: #ddd;
                border-radius: 4px;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

def apply_custom_fonts():
    """
    Injects CSS to enforce Vazirmatn font across the application.
    """
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@100..900&display=swap');
        
        /* Apply font globally to the app */
        html, body, .stApp {
            font-family: 'Vazirmatn', sans-serif !important;
        }
        
        /* Apply to specific text elements but avoid generic containers like div/span 
           to prevent breaking icons (which use ligatures in spans). 
           We rely on inheritance from body for most divs/spans.
        */
        h1, h2, h3, h4, h5, h6, p, label, input, textarea, select, button {
            font-family: 'Vazirmatn', sans-serif !important;
        }

        /* 
           FORCE FULL WIDTH & REMOVE PADDING 
           This targets the main content container in Streamlit.
        */
        .block-container {
            max-width: 100% !important;
            padding-top: 6rem !important;
            padding-bottom: 2rem !important;
            padding-left: 3rem !important;
            padding-right: 3rem !important;
        }

        @media (max-width: 900px) {
            .block-container {
                padding-top: 2rem !important;
                padding-bottom: 1.25rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }
        }

        @media (max-width: 640px) {
            .block-container {
                padding-top: 0.5rem !important;
                padding-bottom: 1rem !important;
                padding-left: 0.7rem !important;
                padding-right: 0.7rem !important;
            }
        }
        
        /* Ensure tooltips and other floating elements get it too if possible, 
           without breaking icons. */
        .stTooltipHoverTarget, .stMarkdown, .stText, div[data-testid="stDialog"] {
            font-family: 'Vazirmatn', sans-serif !important;
        }

        /* Force font on dataframes */
        div[data-testid="stDataFrame"] *, div[data-testid="stTable"] * {
            font-family: 'Vazirmatn', sans-serif !important;
        }

        /* Protect code blocks */
        code, pre, .stCode {
            font-family: 'Source Code Pro', monospace !important;
        }
        
        /* Timer UI */
        .timer-display {
            font-size: 5rem;
            font-weight: 700;
            color: #2E7D32;
            text-align: center;
            padding: 1rem 0;
            font-family: 'Vazirmatn', sans-serif !important;
            font-variant-numeric: tabular-nums;
            letter-spacing: 2px;
            line-height: 1;
            text-shadow: 0 2px 10px rgba(46, 125, 50, 0.2);
        }
        .timer-task-title {
            text-align: center;
            font-size: 1.5rem;
            color: #333;
            margin-bottom: 0.5rem;
            font-weight: 600;
            font-family: 'Vazirmatn', sans-serif !important;
        }
        .timer-subtext {
            text-align: center;
            color: #666;
            font-size: 1rem;
            margin-bottom: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def inject_atlas_styles():
    """Styling tokens for the Atlas timer-first workspace."""
    st.markdown(
        """
        <style>
        :root {
            --atlas-border: #e5dccb;
            --atlas-bg-soft: #fffaf2;
            --atlas-ink: #1f2933;
            --atlas-muted: #5f6b7a;
            --atlas-accent: #8a6827;
            --atlas-emerald: #0f766e;
        }

        .block-container {
            padding-top: 0.75rem !important;
        }

        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"]:first-of-type {
            margin-top: 0 !important;
        }

        .atlas-hero {
            border: 1px solid var(--atlas-border);
            border-radius: 16px;
            padding: 0.95rem 1.1rem;
            background: linear-gradient(128deg, #fffdf7 0%, #f8f1e4 44%, #f0f7f5 100%);
            margin-bottom: 0.75rem;
            box-shadow: 0 10px 26px rgba(39, 34, 26, 0.08);
        }

        .atlas-title {
            margin: 0;
            font-size: 1.1rem;
            color: var(--atlas-ink);
            font-weight: 700;
        }

        .atlas-subtitle {
            margin: 0.2rem 0 0;
            font-size: 0.88rem;
            color: var(--atlas-muted);
        }

        .atlas-pane-title {
            margin: 0.15rem 0 0.35rem;
            color: var(--atlas-ink);
            font-weight: 700;
            letter-spacing: 0.01em;
        }

        .atlas-kicker {
            text-transform: uppercase;
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            color: var(--atlas-accent);
            font-weight: 700;
            margin-bottom: 0.25rem;
        }

        .atlas-meta {
            font-size: 0.82rem;
            color: var(--atlas-muted);
        }

        .atlas-human-note {
            font-size: 0.88rem;
            color: #3c4757;
            line-height: 1.45;
            margin: 0.12rem 0 0.55rem;
        }

        .atlas-luxe-strip {
            height: 4px;
            border-radius: 999px;
            background: linear-gradient(90deg, #8a6827 0%, #d2b26b 50%, #8a6827 100%);
            margin-bottom: 0.65rem;
            opacity: 0.95;
        }

        .atlas-focus-entity {
            font-size: 1.7rem;
            font-weight: 760;
            letter-spacing: 0.01em;
            color: var(--atlas-ink);
            margin: 0.15rem 0 0.65rem;
        }

        .atlas-suggested-line {
            margin: 0.12rem 0 0.15rem;
            color: var(--atlas-ink);
            font-size: 1.02rem;
            line-height: 1.32;
            font-weight: 560;
        }

        .atlas-suggested-label {
            font-weight: 760;
        }

        .atlas-suggested-reason {
            margin: 0 0 0.45rem;
            font-size: 0.86rem;
            color: #6b7280;
            line-height: 1.36;
        }

        .atlas-field-label {
            margin: 0.2rem 0 0.15rem;
            color: #1f2933;
            font-size: 0.82rem;
            font-weight: 650;
        }

        .atlas-stop-composer {
            margin: 0.35rem 0 0.12rem;
            border: 1px solid var(--atlas-border);
            border-radius: 12px;
            background: #fffcf5;
            padding: 0.42rem 0.55rem;
        }

        .atlas-stop-composer-title {
            color: #1f2933;
            font-weight: 700;
            font-size: 0.84rem;
            margin-bottom: 0.1rem;
        }

        .atlas-stop-composer-hint {
            color: #5a6674;
            font-size: 0.77rem;
            line-height: 1.35;
        }

        .atlas-nextup-label {
            margin-top: 0.65rem;
            margin-bottom: 0.2rem;
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--atlas-accent);
        }

        .atlas-spotlight-path {
            margin-top: 0.2rem;
            margin-bottom: 0.12rem;
            color: var(--atlas-muted);
            font-size: 0.8rem;
            letter-spacing: 0.02em;
        }

        .atlas-nav-line {
            margin-top: 0.2rem;
            margin-bottom: 0.35rem;
            color: #4d5a69;
            font-size: 0.86rem;
            letter-spacing: 0.01em;
            font-weight: 560;
        }

        .atlas-spotlight-title {
            margin-top: 0.08rem;
            margin-bottom: 0.08rem;
            color: var(--atlas-ink);
            font-size: 1.22rem;
            font-weight: 740;
        }

        .atlas-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin: 0.15rem 0 0.2rem;
        }

        .atlas-attn-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin-bottom: 0.5rem;
        }

        .atlas-attn-chip {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.08rem 0.5rem;
            border: 1px solid transparent;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            line-height: 1.45;
        }

        .atlas-map-chip {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.08rem 0.5rem;
            border: 1px solid transparent;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            line-height: 1.45;
        }

        .atlas-map-state-legend {
            margin-top: 0.2rem;
            margin-bottom: 0.55rem;
            display: grid;
            gap: 0.28rem;
        }

        .atlas-map-state-item {
            display: inline-flex;
            align-items: center;
            gap: 0.36rem;
            color: #51606f;
            font-size: 0.77rem;
            font-weight: 560;
        }

        .atlas-map-ring {
            width: 0.72rem;
            height: 0.72rem;
            border-radius: 999px;
            display: inline-block;
            background: rgba(255, 255, 255, 0.8);
            border: 2px solid #b4bcc8;
        }

        .atlas-map-ring-focus {
            border-color: #0d9488;
        }

        .atlas-map-ring-selected {
            border-color: #8a6827;
        }

        .atlas-map-ring-path {
            border-color: #b9914a;
        }

        .atlas-map-hatch {
            width: 0.72rem;
            height: 0.72rem;
            border-radius: 0.15rem;
            display: inline-block;
            border: 1px solid #8a6827;
            background-color: #f7eddb;
            background-image: repeating-linear-gradient(
                135deg,
                rgba(47, 38, 18, 0.95) 0px,
                rgba(47, 38, 18, 0.95) 1.2px,
                transparent 1.2px,
                transparent 3.2px
            );
        }

        .atlas-map-needs {
            background: #c36d27;
            border-color: #ad5f20;
            color: #ffffff;
        }

        .atlas-map-ontrack {
            background: #e5d6bb;
            border-color: #cfbe9f;
            color: #493a24;
        }

        .atlas-map-done {
            background: #b5becb;
            border-color: #9eaab9;
            color: #2f3d4c;
        }

        .atlas-attn-overdue {
            background: #fce7e2;
            border-color: #e7b7ac;
            color: #8f2717;
        }

        .atlas-attn-risk {
            background: #fff1de;
            border-color: #f0cca0;
            color: #8b4a0f;
        }

        .atlas-attn-low_progress {
            background: #fff7d8;
            border-color: #ead68d;
            color: #7a6100;
        }

        .atlas-attn-inherited {
            background: #efe8ff;
            border-color: #cebdf7;
            color: #5f3f9f;
        }

        .atlas-attn-on_track {
            background: #e8f8f3;
            border-color: #b8ddd1;
            color: #17665f;
        }

        .atlas-attn-done {
            background: #eef2f7;
            border-color: #cdd6e1;
            color: #4f5c70;
        }

        .atlas-candidate-meta {
            font-size: 0.76rem;
            color: var(--atlas-muted);
            margin: 0.18rem 0 0;
        }

        .atlas-tree-leaf-marker {
            text-align: center;
            color: #96a0ae;
            font-weight: 700;
            font-size: 1.15rem;
            padding-top: 0.2rem;
            opacity: 0.7;
        }

        div[data-testid="stTabs"] button[role="tab"] {
            font-weight: 650;
            color: #6b7280;
        }

        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            color: var(--atlas-accent);
        }

        button[data-testid="stBaseButton-primary"] {
            border: none !important;
            background: linear-gradient(110deg, #0f766e 0%, #129989 100%) !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            box-shadow: 0 6px 14px rgba(15, 118, 110, 0.22);
        }

        [class*="st-key-atlas_spotlight_start_"] button[data-testid="stBaseButton-primary"] {
            background: linear-gradient(120deg, #0f766e 0%, #12a39a 55%, #18b5a8 100%) !important;
            border-radius: 14px !important;
            min-height: 3.1rem !important;
            font-size: 1.02rem !important;
            font-weight: 760 !important;
            letter-spacing: 0.015em;
            box-shadow: 0 10px 24px rgba(14, 116, 107, 0.28), 0 2px 4px rgba(8, 45, 42, 0.16) !important;
            transition: transform 120ms ease, box-shadow 120ms ease, filter 120ms ease;
        }

        [class*="st-key-atlas_spotlight_start_"] button[data-testid="stBaseButton-primary"]:hover {
            transform: translateY(-1px);
            filter: saturate(1.03) brightness(1.02);
            box-shadow: 0 14px 30px rgba(14, 116, 107, 0.34), 0 4px 8px rgba(8, 45, 42, 0.2) !important;
        }

        [class*="st-key-atlas_spotlight_start_"] button[data-testid="stBaseButton-primary"]:active {
            transform: translateY(0);
        }

        button[data-testid="stBaseButton-secondary"] {
            border-color: var(--atlas-border) !important;
            color: var(--atlas-ink) !important;
        }

        button[data-testid="stBaseButton-secondary"] p {
            font-weight: 560 !important;
        }

        [class*="st-key-atlas_stop_with_summary_"] button[data-testid="stBaseButton-primary"] {
            min-height: 2.35rem !important;
            border-radius: 12px !important;
        }

        [class*="st-key-atlas_stop_without_summary_"] button {
            min-height: 2.35rem !important;
            border-radius: 12px !important;
        }

        [class*="st-key-atlas_stop_cancel_"] button {
            min-height: 2.35rem !important;
            border-radius: 12px !important;
        }

        @media (max-width: 900px) {
            .block-container {
                padding-top: 0.45rem !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] {
                padding: 0.5rem 0.65rem !important;
            }

            .atlas-kicker {
                font-size: 0.68rem;
                margin-bottom: 0.15rem;
                letter-spacing: 0.06em;
            }

            .atlas-human-note {
                font-size: 0.83rem;
                margin: 0.08rem 0 0.35rem;
                line-height: 1.36;
            }

            .atlas-luxe-strip {
                height: 3px;
                margin-bottom: 0.42rem;
            }

            .atlas-suggested-line {
                margin: 0.02rem 0 0.08rem;
                font-size: 0.94rem;
                line-height: 1.25;
            }

            .atlas-suggested-reason {
                margin: 0 0 0.3rem;
                font-size: 0.82rem;
            }

            .atlas-field-label {
                margin: 0.14rem 0 0.08rem;
                font-size: 0.78rem;
            }

            .atlas-stop-composer {
                margin: 0.24rem 0 0.08rem;
                padding: 0.32rem 0.45rem;
            }

            .atlas-stop-composer-title {
                font-size: 0.79rem;
            }

            .atlas-stop-composer-hint {
                font-size: 0.72rem;
            }

            .atlas-spotlight-path {
                margin-top: 0.1rem;
                margin-bottom: 0.06rem;
                font-size: 0.74rem;
                letter-spacing: 0.01em;
            }

            .atlas-focus-entity {
                font-size: 1.3rem;
                margin: 0.05rem 0 0.36rem;
                line-height: 1.2;
            }

            .atlas-chip-row {
                margin: 0.06rem 0 0.1rem;
                gap: 0.24rem;
            }

            .atlas-attn-chip,
            .atlas-map-chip {
                font-size: 0.66rem;
                padding: 0.06rem 0.42rem;
            }

            [class*="st-key-atlas_top_suggest_focus_"] button {
                min-height: 1.85rem !important;
                font-size: 0.76rem !important;
                padding: 0.15rem 0.55rem !important;
                line-height: 1.1 !important;
                border-radius: 10px !important;
            }

            [class*="st-key-atlas_stop_with_summary_"] button[data-testid="stBaseButton-primary"] {
                min-height: 2rem !important;
                font-size: 0.78rem !important;
            }

            [class*="st-key-atlas_stop_without_summary_"] button,
            [class*="st-key-atlas_stop_cancel_"] button {
                min-height: 2rem !important;
                font-size: 0.74rem !important;
                padding: 0.12rem 0.4rem !important;
            }

            /* Remove extra whitespace under the map card on narrow screens. */
            [class*="st-key-atlas_focus_treemap_"] {
                margin-bottom: 0 !important;
                padding-bottom: 0 !important;
            }

            [class*="st-key-atlas_focus_treemap_"] div[data-testid="stPlotlyChart"] {
                margin-bottom: 0 !important;
            }
        }

        @media (max-width: 640px) {
            .block-container {
                padding-top: 0.3rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

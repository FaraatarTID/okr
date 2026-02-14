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

        .atlas-nextup-label {
            margin-top: 0.65rem;
            margin-bottom: 0.2rem;
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--atlas-accent);
        }

        .atlas-tree-leaf-marker {
            text-align: center;
            color: #a4acb8;
            font-weight: 700;
            font-size: 1rem;
            padding-top: 0.35rem;
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

        button[data-testid="stBaseButton-secondary"] {
            border-color: var(--atlas-border) !important;
            color: var(--atlas-ink) !important;
        }

        button[data-testid="stBaseButton-secondary"] p {
            font-weight: 560 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

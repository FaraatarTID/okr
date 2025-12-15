import streamlit as st

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
        
        /* Ensure tooltips and other floating elements get it too if possible, 
           without breaking icons. */
        .stTooltipHoverTarget, .stMarkdown, .stText {
            font-family: 'Vazirmatn', sans-serif !important;
        }

        /* Protect code blocks */
        code, pre, .stCode {
            font-family: 'Source Code Pro', monospace !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

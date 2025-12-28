"""
Unified PDF Generator with Automatic Environment Detection
Supports both PDFShift (cloud/deployed) and pdfkit (local Windows)
"""

import os
import sys
import platform
import datetime
import base64
from io import BytesIO
import streamlit as st

# Try importing both libraries
PDFSHIFT_AVAILABLE = False
PDFKIT_AVAILABLE = False

try:
    import requests
    PDFSHIFT_AVAILABLE = True
except ImportError:
    pass

try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except ImportError:
    pass


def is_deployed_environment():
    """
    Detect if running in a deployed/cloud environment (Streamlit Cloud)
    Returns True if deployed, False if local
    """
    # PRIORITY 0: Check for manual override in secrets
    try:
       import streamlit as st
       if 'PDF_METHOD' in st.secrets:
           method = str(st.secrets['PDF_METHOD']).lower()
           if method == 'pdfkit':
               print("🔧 SECRETS: Forcing pdfkit (Local)")
               return False
           elif method == 'pdfshift':
               print("🔧 SECRETS: Forcing PDFShift (Cloud)")
               return True
    except Exception as e:
       pass  # If secrets not available, continue to other detection methods
       
    # Check for Streamlit Cloud specific environment variables
    if os.getenv('STREAMLIT_SHARING_MODE') or os.getenv('IS_STREAMLIT_CLOUD'):
        return True
    
    # Check if pdfshift API key is configured (indicates deployed environment)
    try:
        if 'pdfshift_api_key' in st.secrets:
            return True
    except:
        pass
    
    # Check if running on Windows (likely local development)
    if platform.system() == 'Windows':
        return False
    
    # Default to deployed if uncertain and pdfshift is available
    return PDFSHIFT_AVAILABLE and not PDFKIT_AVAILABLE


def get_base64_font(font_path):
    """Helper function to convert font file to base64 for embedding"""
    try:
        if os.path.exists(font_path):
            with open(font_path, "rb") as font_file:
                return base64.b64encode(font_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Font error: {e}")
    return ""


def generate_pdf_html(report_items, objective_stats, total_time_str, key_results, 
                      direction="RTL", title="Weekly Work Report", time_label="Last 7 Days",
                      report_summary=None, achievements=None):
    """
    Generate HTML content for PDF (common for both methods)
    """
    align = 'right' if direction == 'RTL' else 'left'
    dir_attr = direction.lower()
    
    # Find font path
    font_path = None
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts", "Vazirmatn-Regular.ttf"),
        os.path.join(os.path.dirname(__file__), "assets", "fonts", "Vazirmatn-Regular.ttf"),
        "assets/fonts/Vazirmatn-Regular.ttf",
        "./Vazirmatn-Regular.ttf"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            font_path = path
            break
    
    font_base64 = get_base64_font(font_path) if font_path else ""
    
    html = f"""
<!DOCTYPE html>
<html dir="{dir_attr}">
<head>
    <meta charset="UTF-8">
    <style>
        @font-face {{
            font-family: 'Vazirmatn';
            src: url('data:font/ttf;base64,{font_base64}') format('truetype');
        }}
        body {{
            font-family: 'Vazirmatn', 'Segoe UI', Tahoma, sans-serif;
            font-size: 13px;
            color: #333;
            direction: {dir_attr};
            text-align: {align};
            padding: 1.5cm;
            line-height: 1.4;
        }}
        h1 {{ color: #2c3e50; font-size: 24px; margin-bottom: 5px; border-bottom: 3px solid #3498db; padding-bottom: 10px; display: inline-block; }}
        h2 {{ color: #34495e; font-size: 18px; margin-top: 25px; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
        h3 {{ color: #7f8c8d; font-size: 16px; margin-top: 20px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
        
        /* Modern Table Styling */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        th {{
            background-color: #f8f9fa;
            color: #2c3e50;
            border-bottom: 2px solid #dde2e6;
            padding: 12px 10px;
            font-weight: 600;
            font-size: 12px;
            text-align: {align};
            white-space: nowrap;
        }}
        td {{
            border-bottom: 1px solid #eee;
            padding: 10px 10px;
            vertical-align: top;
            text-align: {align};
        }}
        tr:nth-child(even) {{ background-color: #fafafa; }}
        tr:hover {{ background-color: #f1f1f1; }}
        tr {{ page-break-inside: avoid; }}

        /* KPI Cards */
        .total-box {{
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin: 20px 0;
            font-size: 16px;
            font-weight: bold;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            display: inline-block;
        }}

        /* Status Badges */
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .badge-green {{ background-color: #e8f5e9; color: #2e7d32; }} /* On Track */
        .badge-amber {{ background-color: #fff8e1; color: #f57f17; }} /* At Risk */
        .badge-red {{ background-color: #ffebee; color: #c62828; }}   /* Overdue */
        .badge-gray {{ background-color: #f5f5f5; color: #616161; }}  /* None */

        .text-muted {{ color: #7f8c8d; font-size: 11px; }}
        
        /* Executive Summary Card */
        .exec-summary {{
            background-color: #fff;
            border: 1px solid #e0e0e0;
            border-left: 5px solid #2ecc71;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}

        .page-break {{ page-break-after: always; }}
    </style>
</head>
<body>
    <div id="header">
        <h1 style="border-bottom: 2px solid #2c3e50; padding-bottom: 10px;">{title}</h1>
        <p>Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>

    <div class="total-box">
        Total Time ({time_label}): {total_time_str}
    </div>

"""
    # Executive Summary Section
    if report_summary:
        import markdown
        summary_html = markdown.markdown(report_summary.get("summary_markdown", ""))
        highlights = report_summary.get("highlights", [])
        
        html += f"""
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid #2ecc71;">
        <h2 style="margin-top: 0;">📋 Executive Summary</h2>
        <div style="font-size: 14px; line-height: 1.6;">{summary_html}</div>
"""
        if highlights:
            html += """
        <ul style="margin-top: 15px;">
"""
            for h in highlights:
                html += f"""            <li style="margin-bottom: 5px; font-weight: 500;">{h}</li>"""
            html += """
        </ul>
"""
        html += """
    </div>
"""

    # Achievements Section
    if achievements:
        html += """
    <div style="margin-bottom: 20px;">
        <h3>🏆 Key Achievements</h3>
        <ul style="list-style-type: none; padding: 0;">
"""
        for a in achievements:
             html += f"""
            <li style="padding: 10px; border-bottom: 1px solid #eee; display: flex; align-items: center;">
                <span style="color: #2ecc71; margin-right: 10px; font-size: 1.2em;">✅</span>
                <span style="font-weight: 500;">{a}</span>
            </li>"""
        html += """
        </ul>
    </div>
"""

    html += """
    <h3>Work Log</h3>
"""

    # Table of Tasks
    if report_items:
        html += """
    <table>
        <thead>
            <tr>
                <th>Task</th>
                <th style="width: 15%;">Objective</th>
                <th style="width: 15%;">Key Result</th>
                <th style="width: 100px;">Date/Time</th>
                <th style="width: 60px;">Dur</th>
                <th style="width: 80px;">Deadline</th>
                <th style="width: 25%;">Summary</th>
            </tr>
        </thead>
        <tbody>
"""
        for item in report_items:
            task_name = item.get('Task', 'Untitled')
            date_str = item.get('Date', '')
            time_str = item.get('Time', '')
            duration = item.get('Duration (m)', 0)
            summary = item.get('Summary', '')
            obj_title = item.get('Objective', '-')
            kr_title = item.get('KeyResult', '-')
            deadline = item.get('Deadline', '—')
            
            # Format Date/Time
            date_time_html = f"""
                <div style="font-weight:bold;">{date_str}</div>
                <div class="text-muted">{time_str}</div>
            """
            
            # Format Deadline Badge
            badge_class = "badge-gray"
            if "On Track" in deadline: 
                badge_class = "badge-green"
            elif "At Risk" in deadline:
                badge_class = "badge-amber" 
            elif "Overdue" in deadline:
                badge_class = "badge-red"
            
            deadline_html = f'<span class="badge {badge_class}">{deadline}</span>' if deadline != "—" else "—"

            html += f"""
            <tr>
                <td><strong>{task_name}</strong></td>
                <td>{obj_title}</td>
                <td>{kr_title}</td>
                <td>{date_time_html}</td>
                <td>{duration}m</td>
                <td>{deadline_html}</td>
                <td style="color: #555;">{summary}</td>
            </tr>
"""

        html += """
        </tbody>
    </table>
"""
    else:
        html += """
    <p>No work recorded in the this period.</p>
"""

    # Objective Stats
    html += """
    <h3>Time Distribution by Objective</h3>
"""
    
    if objective_stats:
        sorted_stats = sorted(objective_stats.items(), key=lambda item: item[1], reverse=True)
        total_mins = sum(v for k, v in objective_stats.items())
        
        def fmt(m):
            h = int(m // 60)
            mn = int(m % 60)
            if h > 0: return f"{h}h {mn}m"
            return f"{mn}m"

        html += """
    <table>
        <thead>
            <tr>
                <th>Objective</th>
                <th style="width: 100px;">Time</th>
                <th style="width: 80px;">%</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for obj_title, mins in sorted_stats:
            pct = (mins / total_mins * 100) if total_mins > 0 else 0
            
            html += f"""
            <tr>
                <td>{obj_title}</td>
                <td>{fmt(mins)}</td>
                <td>{pct:.1f}%</td>
            </tr>
"""
        html += """
        </tbody>
    </table>
"""
    else:
        html += """
    <p>No objective data.</p>
"""

    # Key Result Strategic Status
    if key_results:
        html += """
    <h3>Key Result Strategic Status</h3>
    <table>
        <thead>
            <tr>
                <th>Key Result</th>
                <th style="width: 50px;">Prog</th>
                <th style="width: 50px;">Eff</th>
                <th style="width: 50px;">Qual</th>
                <th style="width: 50px;">Full</th>
            </tr>
        </thead>
        <tbody>
"""

        for kr in key_results:
            kr_title = kr.get("title", "Untitled")
            progress = kr.get("progress", 0)
            
            an = kr.get("geminiAnalysis")
            eff_score = "N/A"
            qual_score = "N/A"
            fulfillment = "N/A"
            
            analysis_html = ""
            
            if an and isinstance(an, dict):
                e_val = an.get('efficiency_score')
                q_val = an.get('effectiveness_score')
                o_val = an.get('overall_score')
                
                if e_val is not None: eff_score = f"{e_val}%"
                if q_val is not None: qual_score = f"{q_val}%"
                if o_val is not None: fulfillment = f"{o_val}%"
                
                summary = an.get('summary', '')
                gap = an.get('gap_analysis', '')
                quality = an.get('quality_assessment', '')
                
                if summary or gap or quality:
                    analysis_html = f"""
                    <tr>
                        <td colspan="5" style="background-color: #fcfcfc; padding: 10px 15px; border-top: none;">
                            <div style="font-size: 11px; color: #555;">
                                {f'<p><strong>Summary:</strong> {summary}</p>' if summary else ''}
                                {f'<p><strong>Gap Analysis:</strong> {gap}</p>' if gap else ''}
                                {f'<p><strong>Quality Assessment:</strong> {quality}</p>' if quality else ''}
                            </div>
                        </td>
                    </tr>
"""

            html += f"""
            <tr style="border-bottom: {'none' if analysis_html else '1px solid #dee2e6'};">
                <td>{kr_title}</td>
                <td>{progress}%</td>
                <td>{eff_score}</td>
                <td>{qual_score}</td>
                <td>{fulfillment}</td>
            </tr>
            {analysis_html}
"""
        html += """
        </tbody>
    </table>
"""

    html += """
</body>
</html>
"""
    return html


def generate_pdf_with_pdfshift(html):
    """
    Generate PDF using PDFShift API (for cloud/deployed environments)
    """
    try:
        pdfshift_api_key = st.secrets["pdfshift_api_key"]
        
        response = requests.post(
            "https://api.pdfshift.io/v3/convert/pdf",
            headers={'X-API-Key': pdfshift_api_key},
            json={
                "source": html,
                "sandbox": True,
                "landscape": True,
                "format": "A4",
                "use_print": False
            }
        )
        
        if response.status_code == 200:
            return BytesIO(response.content)
        else:
            print(f"PDFShift API Error: {response.status_code} - {response.text}")
            st.error(f"PDFShift Error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"PDFShift Exception: {e}")
        st.error(f"PDFShift failed: {str(e)}")
        return None


def generate_pdf_with_pdfkit(html):
    """
    Generate PDF using pdfkit (for local Windows environments)
    """
    try:
        # Configure pdfkit for Windows
        if platform.system() == 'Windows':
            # Common wkhtmltopdf installation paths on Windows
            possible_paths = [
                r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe',
                r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe',
                r'wkhtmltopdf'  # If in PATH
            ]
            
            config = None
            for path in possible_paths:
                if os.path.exists(path):
                    config = pdfkit.configuration(wkhtmltopdf=path)
                    break
            
            if not config:
                st.error("⚠️ wkhtmltopdf not found. Please install it from: https://wkhtmltopdf.org/downloads.html")
                return None
        else:
            config = None  # Linux/Mac should have it in PATH
        
        # Generate PDF
        options = {
            'page-size': 'A4',
            'orientation': 'Landscape',
            'encoding': 'UTF-8',
            'no-outline': None,
            'enable-local-file-access': None
        }
        
        pdf_bytes = pdfkit.from_string(html, False, options=options, configuration=config)
        return BytesIO(pdf_bytes)
        
    except Exception as e:
        print(f"pdfkit Exception: {e}")
        st.error(f"pdfkit failed: {str(e)}")
        return None


def generate_weekly_pdf_v2(report_items, objective_stats, total_time_str, key_results, 
                          direction="RTL", title="Weekly Work Report", time_label="Last 7 Days",
                          report_summary=None, achievements=None):
    """
    Main PDF generation function with automatic environment detection
    
    Returns: BytesIO object containing the PDF data, or None if generation fails
    """
    
    # Detect environment
    is_deployed = is_deployed_environment()
    
    # Generate HTML (common for both methods)
    html = generate_pdf_html(
        report_items, objective_stats, total_time_str, key_results,
        direction, title, time_label,
        report_summary, achievements
    )
    
    # Choose appropriate PDF generation method
    if is_deployed:
        print("🌐 Using PDFShift (Cloud Environment)")
        if not PDFSHIFT_AVAILABLE:
            st.error("PDFShift not available. Please install: pip install requests")
            return None
        return generate_pdf_with_pdfshift(html)
    else:
        print("💻 Using pdfkit (Local Environment)")
        if not PDFKIT_AVAILABLE:
            st.error("pdfkit not available. Please install: pip install pdfkit")
            st.info("Also install wkhtmltopdf from: https://wkhtmltopdf.org/downloads.html")
            return None
        return generate_pdf_with_pdfkit(html)


def get_pdf_generator_info():
    """
    Return information about the current PDF generation setup
    """
    is_deployed = is_deployed_environment()
    
    info = {
        'environment': 'Deployed/Cloud' if is_deployed else 'Local',
        'method': 'PDFShift API' if is_deployed else 'pdfkit (wkhtmltopdf)',
        'pdfshift_available': PDFSHIFT_AVAILABLE,
        'pdfkit_available': PDFKIT_AVAILABLE,
        'platform': platform.system()
    }
    
    return info
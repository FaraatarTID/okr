import datetime
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from io import BytesIO
import os

# --- Constants for Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(__file__)) # Assumes utils/pdf_report.py location
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
REGULAR_FONT_PATH = os.path.join(FONTS_DIR, "Vazirmatn-Regular.ttf")
BOLD_FONT_PATH = os.path.join(FONTS_DIR, "Vazirmatn-Bold.ttf")
ITALIC_FONT_PATH = os.path.join(FONTS_DIR, "Vazirmatn-Medium.ttf")

# --- Helper function for clean absolute file URI (Crucial for WeasyPrint) ---
def get_file_uri(path):
    # Get absolute path and force forward slashes for CSS/WeasyPrint
    return os.path.abspath(path).replace('\\', '/')
# --------------------------------------------------------------------------

# --- NEW: Helper function to normalize text (for unseen character issues) ---
def normalize_text(text):
    if not isinstance(text, str):
        text = str(text)
    # Replace non-breaking spaces (U+200C) or other zero-width characters with a regular space
    text = text.replace('\u200c', ' ').replace('\u200d', ' ') 
    return text
# --------------------------------------------------------------------------


def generate_weekly_pdf_v2(report_items, objective_stats, total_time_str, key_results, direction="RTL", title="Weekly Work Report", time_label="Last 7 Days"):
    
    # 1. CSS Styling
    # Load all font variants and apply robust table/RTL styling
    css_string = f"""
    @font-face {{
        font-family: 'Vazirmatn';
        src: url('file:///{get_file_uri(REGULAR_FONT_PATH)}');
        font-weight: normal;
        font-style: normal;
    }}
    @font-face {{
        font-family: 'Vazirmatn';
        src: url('file:///{get_file_uri(BOLD_FONT_PATH)}');
        font-weight: bold;
    }}
    @font-face {{
        font-family: 'Vazirmatn';
        src: url('file:///{get_file_uri(ITALIC_FONT_PATH)}');
        font-style: italic;
    }}
    
    @page {{
        size: A4 landscape;
        margin: 1cm;
        @bottom-center {{
            content: "Page " counter(page);
            font-family: 'Vazirmatn', sans-serif;
            font-size: 9pt;
        }}
    }}
    body {{
        font-family: 'Vazirmatn', sans-serif;
        font-size: 10pt;
        direction: rtl; /* Global RTL */
        text-align: right;
    }}
    h1 {{
        text-align: center;
        color: #2c3e50;
        font-size: 16pt;
        border-bottom: 2px solid #2c3e50;
        padding-bottom: 5px;
    }}
    .meta {{
        font-size: 9pt;
        color: #666;
        direction: ltr; /* Dates look better LTR */
        text-align: left;
    }}
    .total-box {{
        background-color: #e9ecef;
        padding: 10px;
        font-weight: bold;
        text-align: right;
        margin: 10px 0;
        border-radius: 4px;
    }}
    table {{
        width: 100%; /* Default width */
        border-collapse: collapse;
        margin-top: 10px;
        margin-bottom: 20px;
        table-layout: fixed; 
    }}
    th, td {{
        border: 1px solid #dee2e6;
        padding: 6px;
        vertical-align: top;
        font-size: 9pt; /* Shrink content font slightly */
        /* --- FIX: Aggressive word breaking to stop overflow --- */
        overflow-wrap: break-word; 
        word-break: break-word;    
        /* ---------------------------------------------------- */
    }}
    th {{
        background-color: #f8f9fa;
        font-weight: bold;
        text-align: center;
    }}
    /* Column specific alignments */
    .ltr-cell {{
        direction: ltr;
        text-align: left;
    }}
    .center-cell {{
        text-align: center;
    }}
    /* Analysis Text Block */
    .analysis-block {{
        margin-top: 8px; 
        font-size: 9pt; 
        color: #444; 
        border-top: 1px dashed #ccc; 
        padding-top: 4px;
        font-style: italic;
    }}
    """

    # 2. Build HTML Content 
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head><meta charset="UTF-8"></head>
    <body>
        <div class="meta">Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        <h1>{title}</h1>
        
        <div class="total-box">
            Total Time ({time_label}): {total_time_str}
        </div>

        <h3>Work Log (گزارش کار)</h3>
        <table style="width: 98%;"> <!-- FINAL FIX: SHRINK TABLE TO ENSURE FIT -->
            <thead>
                <tr>
                    <th style="width: 15%">وظیفه (Task)</th>      
                    <th style="width: 15%">هدف (Objective)</th>
                    <th style="width: 15%">نتیجه کلیدی (KR)</th>
                    <th style="width: 10%">Date/Time</th>
                    <th style="width: 7%">Duration</th>                
                    <th style="width: 32%">خلاصه (Summary)</th>    
                </tr>
            </thead>
            <tbody>
    """
    
    if report_items:
        for item in report_items:
            # Normalize content before passing to HTML
            task_name = normalize_text(item.get('Task', ''))
            obj_title = normalize_text(item.get('Objective', '-'))
            kr_title = normalize_text(item.get('KeyResult', '-'))
            summary = normalize_text(item.get('Summary', ''))
            
            html_content += f"""
            <tr>
                <td>{task_name}</td>
                <td>{obj_title}</td>
                <td>{kr_title}</td>
                <td class="ltr-cell center-cell">{item.get('Date', '')} {item.get('Time', '')}</td>
                <td class="center-cell ltr-cell">{item.get('Duration (m)', 0)}m</td>
                <td>{summary}</td>
            </tr>
            """
    else:
        html_content += "<tr><td colspan='6'>No work recorded.</td></tr>"

    html_content += """
            </tbody>
        </table>
        
        <h3>Time Distribution by Objective</h3>
        <table>
             <thead>
                <tr>
                    <th>هدف (Objective)</th>
                    <th style="width: 15%">زمان (Time)</th>
                    <th style="width: 10%">%</th>
                </tr>
            </thead>
            <tbody>
    """
    
    if objective_stats:
        sorted_stats = sorted(objective_stats.items(), key=lambda item: item[1], reverse=True)
        total_mins = sum(v for k, v in objective_stats.items())
        
        for title, mins in sorted_stats:
            pct = (mins / total_mins * 100) if total_mins > 0 else 0
            
            h = int(mins // 60)
            mn = int(mins % 60)
            time_str = f"{h}h {mn}m" if h > 0 else f"{mn}m"
            
            html_content += f"""
            <tr>
                <td>{normalize_text(title)}</td>
                <td class="ltr-cell center-cell">{time_str}</td>
                <td class="ltr-cell center-cell">{pct:.1f}%</td>
            </tr>
            """
            
    html_content += """
            </tbody>
        </table>

        <h3>Key Result Strategic Status</h3>
        <table>
             <thead>
                <tr>
                    <th>نتیجه کلیدی (Key Result)</th>
                    <th style="width: 8%">Prog</th>
                    <th style="width: 8%">Eff</th>
                    <th style="width: 8%">Qual</th>
                    <th style="width: 8%">Full</th>
                </tr>
            </thead>
            <tbody>
    """
    
    if key_results:
        for kr in key_results:
            progress = kr.get("progress", 0)
            an = kr.get("geminiAnalysis", {}) or {}
            
            eff = f"{an.get('efficiency_score')}%" if an.get('efficiency_score') is not None else "N/A"
            qual = f"{an.get('effectiveness_score')}%" if an.get('effectiveness_score') is not None else "N/A"
            full = f"{an.get('overall_score')}%" if an.get('overall_score') is not None else "N/A"
            
            summary = normalize_text(an.get('summary', ''))
            gap = normalize_text(an.get('gap_analysis', ''))
            quality = normalize_text(an.get('quality_assessment', ''))
            
            html_content += f"""
            <tr>
                <td>
                    <strong>{normalize_text(kr.get("title", "Untitled"))}</strong>
    """
            if summary or gap or quality:
                html_content += "<div class='analysis-block'>"
                if summary: html_content += f"<p><strong>خلاصه:</strong> {summary}</p>"
                if gap: html_content += f"<p><strong>تحلیل شکاف:</strong> {gap}</p>"
                if quality: html_content += f"<p><strong>کیفیت:</strong> {quality}</p>"
                html_content += "</div>"
            
            html_content += f"""
                </td>
                <td class="ltr-cell center-cell">{progress}%</td>
                <td class="ltr-cell center-cell">{eff}</td>
                <td class="ltr-cell center-cell">{qual}</td>
                <td class="ltr-cell center-cell">{full}</td>
            </tr>
            """

    html_content += """
            </tbody>
        </table>
    </body>
    </html>
    """

    # 3. Generate PDF
    font_config = FontConfiguration()
    pdf_bytes = BytesIO()
    
    HTML(string=html_content, base_url=BASE_DIR).write_pdf(
        pdf_bytes, 
        stylesheets=[CSS(string=css_string, font_config=font_config)],
        font_config=font_config
    )
    
    return pdf_bytes.getvalue()
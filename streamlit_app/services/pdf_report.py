import pdfkit
from io import BytesIO
import datetime
import os
import sys

def generate_weekly_pdf_v2(report_items, objective_stats, total_time_str, key_results, direction="RTL"):
    """
    Generates a PDF for the weekly work report using pdfkit (wkhtmltopdf).
    Returns: BytesIO object containing the PDF data.
    """
    
    align = 'right' if direction == 'RTL' else 'left'
    dir_attr = direction.lower()
    
    # Font path for @font-face
    # wkhtmltopdf usually works best with absolute file paths for local assets
    font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts", "Vazirmatn-Regular.ttf")
    # Ensure forward slashes for CSS url
    font_url = font_path.replace('\\', '/')
    
    html = f"""
    <!DOCTYPE html>
    <html dir="{dir_attr}">
    <head>
        <meta charset="UTF-8">
        <style>
             @font-face {{
                font-family: 'Vazirmatn';
                src: url('file:///{font_url}') format('truetype');
            }}
            body {{
                font-family: 'Vazirmatn', sans-serif;
                font-size: 12px;
                direction: {dir_attr};
                text-align: {align};
                padding: 2cm;
            }}
            h1, h2, h3 {{
                color: #2c3e50;
                margin-top: 20px;
                margin-bottom: 10px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            th {{
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 8px;
                font-weight: bold;
                text-align: {align};
            }}
            td {{
                border: 1px solid #dee2e6;
                padding: 8px;
                text-align: {align};
            }}
            .total-box {{
                background-color: #e9ecef;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                font-size: 14px;
                font-weight: bold;
                text-align: {align};
            }}
            .footer {{
                text-align: center;
                color: #6c757d;
                font-size: 10px;
                position: fixed;
                bottom: 20px;
                width: 100%;
            }}
        </style>
    </head>
    <body>
        <div id="header">
            <h1 style="border-bottom: 2px solid #2c3e50; padding-bottom: 10px;">Weekly Work Report</h1>
            <p>Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>

        <div class="total-box">
            Total Time (Last 7 Days): {total_time_str}
        </div>

        <h3>Work Log</h3>
    """
    
    # Table of Tasks
    if report_items:
        html += """
        <table>
            <thead>
                <tr>
                    <th>Task</th>
                    <th style="width: 120px;">Date/Time</th>
                    <th style="width: 80px;">Duration</th>
                </tr>
            </thead>
            <tbody>
        """
        for item in report_items:
            task_name = item.get('Task', 'Untitled')
            date_str = item.get('Date', '')
            time_str = item.get('Time', '')
            duration = item.get('Duration (m)', 0)
            
            html += f"""
                <tr>
                    <td>{task_name}</td>
                    <td>{date_str} {time_str}</td>
                    <td>{duration}m</td>
                </tr>
            """
        html += """
            </tbody>
        </table>
        """
    else:
        html += "<p>No work recorded in the last 7 days.</p>"

    # Objective Stats
    html += "<h3>Time Distribution by Objective</h3>"
    
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
        
        for title, mins in sorted_stats:
            pct = (mins / total_mins * 100) if total_mins > 0 else 0
            # No reshaping needed for WebKit
            html += f"""
                <tr>
                    <td>{title}</td>
                    <td>{fmt(mins)}</td>
                    <td>{pct:.1f}%</td>
                </tr>
            """
        html += """
            </tbody>
        </table>
        """
    else:
        html += "<p>No objective data.</p>"

    # Key Result Strategic Status
    html += "<h3>Key Result Strategic Status</h3>"
    
    if key_results:
        html += """
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
            title = kr.get("title", "Untitled")
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
                
                # Extract text fields
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
                    <td>{title}</td>
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
    else:
        html += "<p>No Key Results found.</p>"

    html += """
    </body>
    </html>
    """
    
    
    # Generate PDF
    options = {
        'page-size': 'A4',
        'encoding': "UTF-8",
        'no-outline': None,
        'enable-local-file-access': None
    }
    
    # Configure wkhtmltopdf path
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    config = None
    if os.path.exists(path_wkhtmltopdf):
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
    else:
        # Fallback to PATH or other locations if needed, or let pdfkit search check PATH
        # Attempt to find it if not at default location (optional specific logic could go here)
        pass
        
    try:
        # Return BytesIO
        pdf_data = pdfkit.from_string(html, False, options=options, configuration=config)
        return BytesIO(pdf_data)
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return None

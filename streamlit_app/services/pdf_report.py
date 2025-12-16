from weasyprint import HTML, CSS
from io import BytesIO
import datetime


def generate_weekly_pdf_v2(
    report_items,
    objective_stats,
    total_time_str,
    key_results,
    direction="RTL",
    title="Weekly Work Report",
    time_label="Last 7 Days",
):
    """
    Generates a PDF for the weekly work report using WeasyPrint.
    Returns: BytesIO object containing the PDF data.
    """
    
    is_rtl = direction.upper() == "RTL"
    text_align = "right" if is_rtl else "left"
    dir_attr = "rtl" if is_rtl else "ltr"
    
    # ========================
    # BUILD HTML
    # ========================
    html_content = f"""
    <!DOCTYPE html>
    <html dir="{dir_attr}" lang="{"fa" if is_rtl else "en"}">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            @page {{
                size: A4;
                margin: 15mm;
            }}
            
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: Arial, Helvetica, sans-serif;
                font-size: 12px;
                color: #333;
                direction: {dir_attr};
                text-align: {text_align};
                line-height: 1.6;
            }}
            
            h1 {{
                color: #2c3e50;
                font-size: 24px;
                border-bottom: 2px solid #2c3e50;
                padding-bottom: 10px;
                margin-bottom: 10px;
                margin-top: 0;
            }}
            
            h3 {{
                color: #2c3e50;
                font-size: 14px;
                margin-top: 20px;
                margin-bottom: 10px;
            }}
            
            .date {{
                color: #6c757d;
                font-size: 10px;
                margin-bottom: 10px;
            }}
            
            .total-box {{
                background-color: #e9ecef;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
                font-weight: bold;
                font-size: 13px;
                color: #2c3e50;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
                font-size: 10px;
            }}
            
            th {{
                background-color: #f8f9fa;
                color: #2c3e50;
                font-weight: bold;
                padding: 10px;
                border: 1px solid #dee2e6;
                text-align: {text_align};
            }}
            
            td {{
                padding: 8px;
                border: 1px solid #dee2e6;
                text-align: {text_align};
                vertical-align: top;
                word-wrap: break-word;
            }}
            
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            
            tr:nth-child(odd) {{
                background-color: #ffffff;
            }}
            
            .details {{
                font-size: 9px;
                color: #444;
                margin: 8px 0;
                padding: 8px;
                background-color: #fcfcfc;
                border-{("right" if is_rtl else "left")}: 3px solid #dee2e6;
            }}
            
            .footer {{
                margin-top: 30px;
                padding-top: 10px;
                border-top: 1px solid #dee2e6;
                text-align: center;
                font-size: 9px;
                color: #999;
            }}
            
            .no-data {{
                color: #6c757d;
                font-size: 11px;
                margin: 15px 0;
            }}
        </style>
    </head>
    <body>
        <h1>{title}</h1>
        <p class="date">Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        
        <div class="total-box">
            Total Time ({time_label}): {total_time_str}
        </div>
        
        <h3>Work Log</h3>
    """
    
    # ========================
    # WORK LOG TABLE
    # ========================
    if report_items:
        html_content += """
        <table>
            <thead>
                <tr>
                    <th style="width: 18%;">Task</th>
                    <th style="width: 15%;">Objective</th>
                    <th style="width: 15%;">Key Result</th>
                    <th style="width: 18%;">Date/Time</th>
                    <th style="width: 10%;">Duration</th>
                    <th style="width: 24%;">Summary</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for item in report_items:
            task = str(item.get('Task', 'Untitled'))[:40].replace('<', '&lt;').replace('>', '&gt;')
            objective = str(item.get('Objective', '-'))[:20].replace('<', '&lt;').replace('>', '&gt;')
            key_result = str(item.get('KeyResult', '-'))[:20].replace('<', '&lt;').replace('>', '&gt;')
            datetime_str = f"{item.get('Date', '')} {item.get('Time', '')}"[:22]
            duration = f"{item.get('Duration (m)', 0)}m"
            summary = str(item.get('Summary', ''))[:50].replace('<', '&lt;').replace('>', '&gt;')
            
            html_content += f"""
                <tr>
                    <td>{task}</td>
                    <td>{objective}</td>
                    <td>{key_result}</td>
                    <td>{datetime_str}</td>
                    <td>{duration}</td>
                    <td>{summary}</td>
                </tr>
            """
        
        html_content += """
            </tbody>
        </table>
        """
    else:
        html_content += '<p class="no-data">No work recorded in the selected period.</p>'
    
    # ========================
    # OBJECTIVE STATS TABLE
    # ========================
    html_content += "<h3>Time Distribution by Objective</h3>"
    
    if objective_stats:
        total_mins = sum(objective_stats.values())
        
        def format_time(minutes):
            hours = int(minutes // 60)
            mins = int(minutes % 60)
            if hours > 0:
                return f"{hours}h {mins}m"
            return f"{mins}m"
        
        html_content += """
        <table>
            <thead>
                <tr>
                    <th style="width: 60%;">Objective</th>
                    <th style="width: 20%;">Time</th>
                    <th style="width: 20%;">Percentage</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for obj, mins in sorted(objective_stats.items(), key=lambda x: x[1], reverse=True):
            pct = (mins / total_mins * 100) if total_mins else 0
            obj_name = str(obj)[:40].replace('<', '&lt;').replace('>', '&gt;')
            
            html_content += f"""
                <tr>
                    <td>{obj_name}</td>
                    <td>{format_time(mins)}</td>
                    <td>{pct:.1f}%</td>
                </tr>
            """
        
        html_content += """
            </tbody>
        </table>
        """
    else:
        html_content += '<p class="no-data">No objective data.</p>'
    
    # ========================
    # KEY RESULTS TABLE
    # ========================
    if key_results:
        html_content += """
        <h3>Key Result Strategic Status</h3>
        <table>
            <thead>
                <tr>
                    <th style="width: 35%;">Key Result</th>
                    <th style="width: 13%;">Progress</th>
                    <th style="width: 13%;">Efficiency</th>
                    <th style="width: 13%;">Effectiveness</th>
                    <th style="width: 13%;">Overall</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for kr in key_results:
            analysis = kr.get("geminiAnalysis") or {}
            kr_title = str(kr.get("title", "Untitled"))[:40].replace('<', '&lt;').replace('>', '&gt;')
            
            html_content += f"""
                <tr>
                    <td>{kr_title}</td>
                    <td>{kr.get('progress', 0)}%</td>
                    <td>{analysis.get('efficiency_score', 'N/A')}%</td>
                    <td>{analysis.get('effectiveness_score', 'N/A')}%</td>
                    <td>{analysis.get('overall_score', 'N/A')}%</td>
                </tr>
            """
            
            # Add analysis details
            details_html = ""
            if analysis.get("summary"):
                summary_text = str(analysis['summary'])[:120].replace('<', '&lt;').replace('>', '&gt;')
                details_html += f"<strong>Summary:</strong> {summary_text}<br/>"
            if analysis.get("gap_analysis"):
                gap_text = str(analysis['gap_analysis'])[:120].replace('<', '&lt;').replace('>', '&gt;')
                details_html += f"<strong>Gap Analysis:</strong> {gap_text}<br/>"
            if analysis.get("quality_assessment"):
                quality_text = str(analysis['quality_assessment'])[:120].replace('<', '&lt;').replace('>', '&gt;')
                details_html += f"<strong>Quality Assessment:</strong> {quality_text}"
            
            if details_html:
                html_content += f'<tr><td colspan="5" class="details">{details_html}</td></tr>'
        
        html_content += """
            </tbody>
        </table>
        """
    
    # ========================
    # FOOTER
    # ========================
    html_content += """
        <div class="footer">
            Generated by Weekly Report System
        </div>
    </body>
    </html>
    """
    
    # ========================
    # CONVERT TO PDF USING WEASYPRINT
    # ========================
    try:
        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        return pdf_buffer
    except Exception as e:
        raise Exception(f"PDF generation failed: {str(e)}")
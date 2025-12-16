from weasyprint import HTML, CSS
from io import BytesIO
import datetime
import os


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

    align = "right" if direction.upper() == "RTL" else "left"
    dir_attr = direction.lower()

    # Absolute path to font (required for WeasyPrint)
    base_dir = os.path.dirname(os.path.dirname(__file__))
    font_path = os.path.join(
        base_dir, "assets", "fonts", "Vazirmatn-Regular.ttf"
    )

    if not os.path.exists(font_path):
        raise FileNotFoundError(f"Font not found: {font_path}")

    html = f"""
    <!DOCTYPE html>
    <html dir="{dir_attr}">
    <head>
        <meta charset="utf-8">
        <style>
            @font-face {{
                font-family: 'Vazirmatn';
                src: url('{font_path}');
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

            th, td {{
                border: 1px solid #dee2e6;
                padding: 8px;
                text-align: {align};
                vertical-align: top;
            }}

            th {{
                background-color: #f8f9fa;
                font-weight: bold;
            }}

            .total-box {{
                background-color: #e9ecef;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                font-size: 14px;
                font-weight: bold;
            }}

            .footer {{
                position: fixed;
                bottom: 1cm;
                left: 0;
                right: 0;
                text-align: center;
                font-size: 10px;
                color: #6c757d;
            }}
        </style>
    </head>
    <body>

        <h1 style="border-bottom: 2px solid #2c3e50; padding-bottom: 10px;">
            {title}
        </h1>
        <p>Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

        <div class="total-box">
            Total Time ({time_label}): {total_time_str}
        </div>

        <h3>Work Log</h3>
    """

    # ------------------------
    # Work Log Table
    # ------------------------
    if report_items:
        html += """
        <table>
            <thead>
                <tr>
                    <th>Task</th>
                    <th style="width: 15%;">Objective</th>
                    <th style="width: 15%;">Key Result</th>
                    <th style="width: 120px;">Date/Time</th>
                    <th style="width: 60px;">Dur</th>
                    <th style="width: 25%;">Summary</th>
                </tr>
            </thead>
            <tbody>
        """

        for item in report_items:
            html += f"""
            <tr>
                <td>{item.get('Task', 'Untitled')}</td>
                <td>{item.get('Objective', '-')}</td>
                <td>{item.get('KeyResult', '-')}</td>
                <td>{item.get('Date', '')} {item.get('Time', '')}</td>
                <td>{item.get('Duration (m)', 0)}m</td>
                <td>{item.get('Summary', '')}</td>
            </tr>
            """

        html += """
            </tbody>
        </table>
        """
    else:
        html += "<p>No work recorded in the selected period.</p>"

    # ------------------------
    # Objective Stats
    # ------------------------
    html += "<h3>Time Distribution by Objective</h3>"

    if objective_stats:
        total_mins = sum(objective_stats.values())

        def fmt(m):
            h = int(m // 60)
            mn = int(m % 60)
            return f"{h}h {mn}m" if h else f"{mn}m"

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

        for obj, mins in sorted(
            objective_stats.items(), key=lambda x: x[1], reverse=True
        ):
            pct = (mins / total_mins * 100) if total_mins else 0
            html += f"""
            <tr>
                <td>{obj}</td>
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

    # ------------------------
    # Key Results
    # ------------------------
    if key_results:
        html += "<h3>Key Result Strategic Status</h3>"
        html += """
        <table>
            <thead>
                <tr>
                    <th>Key Result</th>
                    <th>Prog</th>
                    <th>Eff</th>
                    <th>Qual</th>
                    <th>Full</th>
                </tr>
            </thead>
            <tbody>
        """

        for kr in key_results:
            an = kr.get("geminiAnalysis") or {}

            html += f"""
            <tr>
                <td>{kr.get("title", "Untitled")}</td>
                <td>{kr.get("progress", 0)}%</td>
                <td>{an.get("efficiency_score", "N/A")}%</td>
                <td>{an.get("effectiveness_score", "N/A")}%</td>
                <td>{an.get("overall_score", "N/A")}%</td>
            </tr>
            """

            details = []
            if an.get("summary"):
                details.append(f"<p><strong>Summary:</strong> {an['summary']}</p>")
            if an.get("gap_analysis"):
                details.append(f"<p><strong>Gap:</strong> {an['gap_analysis']}</p>")
            if an.get("quality_assessment"):
                details.append(
                    f"<p><strong>Quality:</strong> {an['quality_assessment']}</p>"
                )

            if details:
                html += f"""
                <tr>
                    <td colspan="5" style="background:#fcfcfc;">
                        {''.join(details)}
                    </td>
                </tr>
                """

        html += """
            </tbody>
        </table>
        """

    html += """
        <div class="footer">
            Generated by Weekly Report System
        </div>
    </body>
    </html>
    """

    # ------------------------
    # PDF Generation
    # ------------------------
    pdf_bytes = HTML(string=html).write_pdf()

    return BytesIO(pdf_bytes)

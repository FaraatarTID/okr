"""
PDF Service for OKR Application.
Uses fpdf2 for PDF generation (no external binary dependencies).
"""
from fpdf import FPDF
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Any, Optional
import os


class OKRReport(FPDF):
    """Custom PDF class for OKR reports with consistent styling."""
    
    def __init__(self, title: str = "OKR Report", direction: str = "LTR"):
        super().__init__()
        self.report_title = title
        self.direction = direction
        self._setup_fonts()
        
    def _setup_fonts(self):
        """Setup fonts including support for Persian/Arabic text."""
        # Try to load Vazirmatn font for RTL support
        font_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "assets", "fonts", "Vazirmatn-Regular.ttf"
        )
        
        if os.path.exists(font_path):
            self.add_font("Vazirmatn", "", font_path, uni=True)
            self.default_font = "Vazirmatn"
        else:
            # Fallback to built-in font
            self.default_font = "Helvetica"
    
    def header(self):
        """Page header."""
        self.set_font(self.default_font, "B", 16)
        self.cell(0, 10, self.report_title, ln=True, align="C")
        self.set_font(self.default_font, "", 10)
        self.cell(0, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
        self.ln(5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)
    
    def footer(self):
        """Page footer."""
        self.set_y(-15)
        self.set_font(self.default_font, "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")
    
    def section_title(self, title: str):
        """Add a section title."""
        self.ln(5)
        self.set_font(self.default_font, "B", 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 8, title, ln=True, fill=True)
        self.ln(2)
    
    def add_key_value(self, key: str, value: str):
        """Add a key-value pair row."""
        self.set_font(self.default_font, "B", 10)
        self.cell(50, 6, key + ":", align="L")
        self.set_font(self.default_font, "", 10)
        self.cell(0, 6, str(value), ln=True)
    
    def add_table_header(self, headers: List[str], widths: List[int]):
        """Add a table header row."""
        self.set_font(self.default_font, "B", 9)
        self.set_fill_color(230, 230, 230)
        
        for header, width in zip(headers, widths):
            self.cell(width, 7, header, border=1, fill=True, align="C")
        self.ln()
    
    def add_table_row(self, cells: List[str], widths: List[int]):
        """Add a table data row."""
        self.set_font(self.default_font, "", 9)
        
        for cell, width in zip(cells, widths):
            # Truncate long text
            display_text = str(cell)[:30] + "..." if len(str(cell)) > 30 else str(cell)
            self.cell(width, 6, display_text, border=1, align="L")
        self.ln()


def generate_weekly_report(
    report_items: List[Dict[str, Any]],
    objective_stats: Dict[str, int],
    total_time_str: str,
    key_results: List[Dict[str, Any]],
    direction: str = "LTR",
    title: str = "Weekly Work Report",
    time_label: str = "Last 7 Days"
) -> Optional[BytesIO]:
    """
    Generate a PDF weekly work report.
    
    Args:
        report_items: List of work log entries
        objective_stats: Dict of objective -> minutes spent
        total_time_str: Formatted total time string
        key_results: List of key result data with analysis
        direction: "RTL" or "LTR"
        title: Report title
        time_label: Time period label
    
    Returns:
        BytesIO containing PDF data, or None on error
    """
    try:
        pdf = OKRReport(title=title, direction=direction)
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Total Time Box
        pdf.set_fill_color(200, 230, 200)
        pdf.set_font(pdf.default_font, "B", 12)
        pdf.cell(0, 10, f"Total Time ({time_label}): {total_time_str}", ln=True, fill=True, align="C")
        pdf.ln(5)
        
        # Work Log Section
        pdf.section_title("Work Log")
        
        if report_items:
            headers = ["Task", "Objective", "Date", "Duration", "Summary"]
            widths = [50, 40, 25, 20, 55]
            pdf.add_table_header(headers, widths)
            
            for item in report_items:
                row = [
                    item.get("Task", "Untitled"),
                    item.get("Objective", "-"),
                    item.get("Date", ""),
                    f"{item.get('Duration (m)', 0)}m",
                    item.get("Summary", "")
                ]
                pdf.add_table_row(row, widths)
        else:
            pdf.set_font(pdf.default_font, "I", 10)
            pdf.cell(0, 10, "No work recorded in this period.", ln=True)
        
        pdf.ln(5)
        
        # Time Distribution Section
        pdf.section_title("Time Distribution by Objective")
        
        if objective_stats:
            headers = ["Objective", "Time", "Percentage"]
            widths = [100, 40, 50]
            pdf.add_table_header(headers, widths)
            
            total_mins = sum(objective_stats.values())
            sorted_stats = sorted(objective_stats.items(), key=lambda x: x[1], reverse=True)
            
            for obj_title, mins in sorted_stats:
                pct = (mins / total_mins * 100) if total_mins > 0 else 0
                hours = int(mins // 60)
                remaining_mins = int(mins % 60)
                time_str = f"{hours}h {remaining_mins}m" if hours > 0 else f"{remaining_mins}m"
                
                pdf.add_table_row([obj_title, time_str, f"{pct:.1f}%"], widths)
        else:
            pdf.set_font(pdf.default_font, "I", 10)
            pdf.cell(0, 10, "No objective data available.", ln=True)
        
        pdf.ln(5)
        
        # Key Result Strategic Status
        if key_results:
            pdf.section_title("Key Result Strategic Status")
            
            headers = ["Key Result", "Progress", "Efficiency", "Effectiveness"]
            widths = [80, 35, 35, 40]
            pdf.add_table_header(headers, widths)
            
            for kr in key_results:
                progress = f"{kr.get('progress', 0)}%"
                
                analysis = kr.get("geminiAnalysis", {})
                if isinstance(analysis, str):
                    try:
                        import json
                        analysis = json.loads(analysis)
                    except:
                        analysis = {}
                
                eff = f"{analysis.get('efficiency_score', 'N/A')}%" if analysis.get('efficiency_score') else "N/A"
                effect = f"{analysis.get('effectiveness_score', 'N/A')}%" if analysis.get('effectiveness_score') else "N/A"
                
                pdf.add_table_row([
                    kr.get("title", "Untitled"),
                    progress,
                    eff,
                    effect
                ], widths)
                
                # Add analysis summary if available
                summary = analysis.get("summary", "")
                if summary:
                    pdf.set_font(pdf.default_font, "I", 8)
                    pdf.set_text_color(100)
                    pdf.multi_cell(0, 4, f"  Summary: {summary}")
                    pdf.set_text_color(0)
        
        # Time Analytics Section
        pdf.ln(5)
        pdf.section_title("Time Analytics Summary")
        
        if objective_stats:
            total_mins = sum(objective_stats.values())
            total_hours = total_mins / 60
            avg_per_objective = total_mins / len(objective_stats) if objective_stats else 0
            
            pdf.add_key_value("Total Hours Logged", f"{total_hours:.1f} hours")
            pdf.add_key_value("Objectives Worked On", str(len(objective_stats)))
            pdf.add_key_value("Avg Time per Objective", f"{avg_per_objective:.0f} minutes")
            
            # Find most worked objective
            if objective_stats:
                top_obj = max(objective_stats.items(), key=lambda x: x[1])
                pdf.add_key_value("Most Time Spent On", f"{top_obj[0]} ({top_obj[1]:.0f}m)")
        
        # Generate PDF bytes
        pdf_bytes = pdf.output()
        return BytesIO(pdf_bytes)
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return None


def generate_goal_report(
    goal_title: str,
    strategies: List[Dict[str, Any]],
    total_progress: int
) -> Optional[BytesIO]:
    """
    Generate a PDF report for a specific Goal.
    
    Args:
        goal_title: Goal title
        strategies: List of strategy data with nested objectives/KRs
        total_progress: Overall goal progress percentage
    
    Returns:
        BytesIO containing PDF data, or None on error
    """
    try:
        pdf = OKRReport(title=f"Goal Report: {goal_title}")
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Goal Overview
        pdf.section_title("Goal Overview")
        pdf.add_key_value("Goal", goal_title)
        pdf.add_key_value("Overall Progress", f"{total_progress}%")
        pdf.add_key_value("Strategies", str(len(strategies)))
        
        # Progress bar visualization
        pdf.ln(3)
        pdf.set_fill_color(200, 200, 200)
        pdf.cell(150, 8, "", border=1, fill=True)
        pdf.set_xy(pdf.get_x() - 150, pdf.get_y())
        pdf.set_fill_color(76, 175, 80)  # Green
        pdf.cell(int(150 * total_progress / 100), 8, "", fill=True)
        pdf.ln(10)
        
        # Strategies breakdown
        for i, strategy in enumerate(strategies, 1):
            pdf.section_title(f"Strategy {i}: {strategy.get('title', 'Untitled')}")
            
            objectives = strategy.get("objectives", [])
            if objectives:
                headers = ["Objective", "Progress", "Key Results"]
                widths = [80, 30, 80]
                pdf.add_table_header(headers, widths)
                
                for obj in objectives:
                    krs = obj.get("key_results", [])
                    kr_summary = f"{len(krs)} KRs" if krs else "No KRs"
                    
                    pdf.add_table_row([
                        obj.get("title", "Untitled"),
                        f"{obj.get('progress', 0)}%",
                        kr_summary
                    ], widths)
            else:
                pdf.set_font(pdf.default_font, "I", 10)
                pdf.cell(0, 8, "No objectives defined.", ln=True)
        
        pdf_bytes = pdf.output()
        return BytesIO(pdf_bytes)
        
    except Exception as e:
        print(f"Error generating goal report: {e}")
        return None

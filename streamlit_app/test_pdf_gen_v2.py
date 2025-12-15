
import sys
import os
# Add the directory containing 'services' to the path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from services.pdf_report import generate_weekly_pdf_v2

def test_generation():
    print("Testing PDF generation...")
    
    report_items = [
        {'Task': 'Test Task 1', 'Date': '2023-10-27', 'Time': '10:00', 'Duration (m)': 60},
        {'Task': 'Test Task 2', 'Date': '2023-10-27', 'Time': '11:00', 'Duration (m)': 30}
    ]
    objective_stats = {'Objective 1': 60, 'Objective 2': 30}
    total_time_str = "1h 30m"
    key_results = [{'title': 'KR 1', 'progress': 50, 'geminiAnalysis': {'efficiency_score': 80, 'overall_score': 90}}]
    
    try:
        pdf_bytes = generate_weekly_pdf_v2(report_items, objective_stats, total_time_str, key_results)
        if pdf_bytes:
            print("PDF generated successfully.")
            output_file = "test_output_configured.pdf"
            with open(output_file, "wb") as f:
                f.write(pdf_bytes.getvalue())
            print(f"Saved to {output_file}")
        else:
            print("PDF generation failed (returned None).")
    except Exception as e:
        print(f"Exception during generation: {e}")

if __name__ == "__main__":
    test_generation()

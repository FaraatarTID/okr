
import sys
import os
# Add the directory containing 'services' to the path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from services.pdf_report import generate_weekly_pdf_v2

def test_generation():
    print("Testing PDF generation with analysis...")
    
    report_items = [
        {'Task': 'Test Task 1', 'Date': '2023-10-27', 'Time': '10:00', 'Duration (m)': 60}
    ]
    objective_stats = {'Objective 1': 60}
    total_time_str = "1h 00m"
    key_results = [
        {
            'title': 'KR 1 with Analysis', 
            'progress': 50, 
            'geminiAnalysis': {
                'efficiency_score': 80, 
                'overall_score': 90,
                'summary': 'This is a summary of the analysis.',
                'gap_analysis': 'We are missing some key tasks here.',
                'quality_assessment': 'The quality is good but needs improvement.'
            }
        },
        {
            'title': 'KR 2 without Analysis', 
            'progress': 20
        }
    ]
    
    try:
        pdf_bytes = generate_weekly_pdf_v2(report_items, objective_stats, total_time_str, key_results)
        if pdf_bytes:
            print("PDF generated successfully.")
            output_file = "test_output_analysis.pdf"
            with open(output_file, "wb") as f:
                f.write(pdf_bytes.getvalue())
            print(f"Saved to {output_file}")
        else:
            print("PDF generation failed (returned None).")
    except Exception as e:
        print(f"Exception during generation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_generation()

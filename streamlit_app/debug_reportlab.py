try:
    import reportlab
    print(f"ReportLab Version: {reportlab.Version}")
    print(f"File: {reportlab.__file__}")

    import reportlab.pdfbase.ttfonts
    print("Imported reportlab.pdfbase.ttfonts")
    print(dir(reportlab.pdfbase.ttfonts))
    
    from reportlab.pdfbase.ttfonts import TTFFont
    print("Successfully imported TTFFont")
except Exception as e:
    print(f"Error: {e}")

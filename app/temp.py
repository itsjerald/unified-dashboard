import pdfplumber

with pdfplumber.open("C:/Users/pjerald-0534/Downloads/gpay_statement_20251001_20251031.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        print("--- PAGE", i+1, "---")
        print(page.extract_text())
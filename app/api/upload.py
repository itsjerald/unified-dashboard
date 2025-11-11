# app/api/upload.py

from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from sqlmodel import Session, select as sqlselect
from app.auth import get_current_user
from app.models import Transaction
from app.db import engine
from datetime import datetime
import hashlib, csv, json, io

router = APIRouter()

# ----------------------------
# Category Detection
# ----------------------------
def detect_category(merchant_name: str):
    if not merchant_name:
        return "Other"

    name = merchant_name.lower()
    mapping = {
        "Medical": ["medplus", "pharma", "chemist", "hospital"],
        "Groceries": ["vegetable", "fruit", "grocery", "supermarket", "mart"],
        "Fuel": ["hp", "indian oil", "indianoil", "shell", "petrol"],
        "Food": ["hotel", "restaurant", "biryani", "grill", "cafe"],
        "Shopping": ["mobile", "electronics", "clothing", "store"],
        "Finance": ["zerodha", "bank", "broker", "mutual"],
        "Family": ["jenitha", "ashok", "amma", "dad"],
    }

    for category, keywords in mapping.items():
        if any(k in name for k in keywords):
            return category

    return "Other"


def txn_hash(txn_id: str, date_iso: str, amount: float):
    s = f"{txn_id}|{date_iso}|{amount}"
    return hashlib.sha256(s.encode("utf8")).hexdigest()


@router.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    content = await file.read()

    # read as text
    try:
        text = content.decode("utf-8")
    except:
        text = None

    records = []

    # ---------------- JSON ----------------
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "transactions" in parsed:
                records = parsed["transactions"]
            elif isinstance(parsed, list):
                records = parsed
        except:
            pass

    # ---------------- CSV ----------------
    if not records and text:
        try:
            s = io.StringIO(text)
            for row in csv.DictReader(s):
                records.append(row)
        except:
            pass

    # ---------------- PDF ----------------
    if not records:
        import pdfplumber, re
        pdf = pdfplumber.open(io.BytesIO(content))
        text_data = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_data += t + "\n"
        pdf.close()

        lines = [ln.strip() for ln in text_data.split("\n") if ln.strip()]
        date_pattern = re.compile(r"(\d{2}\w{3},\d{4})")

        txns = []
        i = 0
        while i < len(lines):
            line = lines[i]
            match = date_pattern.search(line)
            if match:
                date_str = match.group(1)
                try:
                    date = datetime.strptime(date_str, "%d%b,%Y")
                except:
                    i += 1
                    continue

                amt_match = re.search(r"₹\s?([0-9,]+)", line)
                if not amt_match:
                    i += 1
                    continue

                amount = float(amt_match.group(1).replace(",", ""))
                desc = line[len(date_str):].strip()

                ref_line = lines[i + 1] if i + 1 < len(lines) else ""
                ref_match = re.search(r"UPITransactionID[: ]?(\d+)", ref_line)
                txn_id = ref_match.group(1) if ref_match else ""

                txns.append({
                    "id": txn_id,
                    "date": date.isoformat(),
                    "amount": amount,
                    "merchant": desc,
                })

                i += 3
            else:
                i += 1

        records = txns

    if not records:
        raise HTTPException(400, "Could not parse file")

    imported = 0
    duplicates = 0

    with Session(engine) as session:
        for r in records:
            txn_id = r.get("id") or ""
            date_raw = r.get("date")
            try:
                dt = datetime.fromisoformat(date_raw)
            except:
                dt = datetime.utcnow()

            amount = float(r.get("amount") or 0)
            merchant = r.get("merchant") or ""
            category = detect_category(merchant)

            h = txn_hash(txn_id, dt.isoformat(), amount)

            try:
                t = Transaction(
                    user_id=user.id,
                    txn_id=txn_id,
                    txn_hash=h,
                    date=dt,
                    amount=amount,
                    merchant=merchant,
                    category=category,
                )
                session.add(t)
                session.commit()
                imported += 1
            except:
                duplicates += 1
                session.rollback()

    return {"imported": imported, "duplicates": duplicates}

import os
import uuid
import csv
import time
import logging
from typing import List, Dict, Tuple
from io import StringIO
from fastapi import FastAPI, File, UploadFile, HTTPException
import requests

app = FastAPI()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@app.get("/", status_code=200)
async def landing():
    """Basic landing / health endpoint returning OK."""
    return {"status": "ok"}

HOSPITAL_API_BASE = "https://hospital-directory.onrender.com"
MAX_CSV_SIZE = int(os.getenv("MAX_CSV_SIZE", 20))
REQUIRED_HEADERS = {"name", "address"}

def validate_csv_headers(headers: List[str]) -> bool:
    if headers is None:
        return False
    return REQUIRED_HEADERS.issubset(set(headers))

async def parse_csv_file(contents: bytes) -> Tuple[List[Dict], List[str]]:
    try:
        text = contents.decode('utf-8')
        reader = csv.DictReader(StringIO(text))
        hospitals = list(reader)
        return hospitals, reader.fieldnames
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid UTF-8 encoding")
    except Exception as e:
        logger.error(f"CSV parsing error: {e}")
        raise HTTPException(status_code=400, detail="Invalid CSV format")

@app.post("/hospitals/bulk/validate")
async def validate_csv(csv_file: UploadFile = File(...)):
    contents = await csv_file.read()
    hospitals, headers = await parse_csv_file(contents)
    
    if not validate_csv_headers(headers):
        raise HTTPException(status_code=400, detail="CSV missing required headers: name, address")
    if len(hospitals) > MAX_CSV_SIZE:
        raise HTTPException(status_code=400, detail=f"CSV exceeds max hospital count ({MAX_CSV_SIZE})")
    
    return {"status": "valid", "count": len(hospitals)}

@app.post("/hospitals/bulk")
async def bulk_create_hospitals(csv_file: UploadFile = File(...)):
    start_time = time.time()
    contents = await csv_file.read()
    hospitals, headers = await parse_csv_file(contents)
    
    if not validate_csv_headers(headers):
        raise HTTPException(status_code=400, detail="CSV missing required headers: name, address")
    if len(hospitals) > MAX_CSV_SIZE:
        raise HTTPException(status_code=400, detail=f"CSV exceeds max hospital count ({MAX_CSV_SIZE})")
    
    batch_id = str(uuid.uuid4())
    processed = []
    failures = []
    for idx, hosp in enumerate(hospitals, 1):
        payload = {
            "name": hosp["name"],
            "address": hosp["address"],
            "phone": hosp.get("phone", ""),
            "creation_batch_id": batch_id,
            "active": False
        }
        try:
            resp = requests.post(f"{HOSPITAL_API_BASE}/hospitals", json=payload, timeout=10)
            if resp.ok:
                result = resp.json()
                processed.append({
                    "row": idx,
                    "hospital_id": result.get("id"),
                    "name": hosp.get("name"),
                    "status": "created"
                })
            else:
                failures.append({"row": idx, "status_code": resp.status_code, "body": resp.text})
                logger.warning("Upstream create failed for row %s: %s", idx, resp.status_code)
        except requests.RequestException as e:
            failures.append({"row": idx, "error": str(e)})
            logger.error("Request exception for row %s: %s", idx, e)
    try:
        activate_resp = requests.patch(f"{HOSPITAL_API_BASE}/hospitals/batch/{batch_id}/activate", timeout=10)
        batch_activated = activate_resp.ok
        if not batch_activated:
            logger.warning("Batch activation returned status %s for batch %s", activate_resp.status_code, batch_id)
    except requests.RequestException as e:
        batch_activated = False
        logger.error("Batch activation failed for %s: %s", batch_id, e)
    end_time = time.time()
    return {
        "batch_id": batch_id,
        "total_hospitals": len(hospitals),
        "processed_hospitals": len(processed),
        "failed_hospitals": len(failures),
        "processing_time_seconds": int(end_time - start_time),
        "batch_activated": batch_activated,
        "hospitals": processed,
        "failures": failures if failures else None
    }

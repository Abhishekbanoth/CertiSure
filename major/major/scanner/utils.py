import os
import json
import fitz  # PyMuPDF
import shutil
import requests
import re
import io
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# Define folders
ORIGINAL_DIR = "media/original"
FAKE_DIR = "media/fake"
UPLOAD_DIR = "media/uploads"
os.makedirs(ORIGINAL_DIR, exist_ok=True)
os.makedirs(FAKE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

file_move_lock = Lock()

# --- Extract Text Using PyMuPDF ---
def extract_text_from_pdf(pdf_path):
    document = fitz.open(pdf_path)
    text = ""
    for page in document:
        words = page.get_text("words")
        text += " ".join(w[4] for w in words) + " "
    document.close()
    text = text.replace("\n", " ").replace("  ", " ").strip()
    return text

# --- Extract QR Code Data Using External API (In-Memory) ---
def extract_qr_from_pdf(pdf_path):
    document = fitz.open(pdf_path)
    qr_data_list = []

    for page_number in range(len(document)):
        page = document[page_number]
        images = page.get_images(full=True)

        for img_index, img in enumerate(images, start=1):
            xref = img[0]
            base_image = document.extract_image(xref)
            image_bytes = base_image["image"]

            files = {'file': ('image.png', io.BytesIO(image_bytes), 'image/png')}
            try:
                response = requests.post('https://api.qrserver.com/v1/read-qr-code/', files=files)
                result = response.json()
                qr_data = result[0]['symbol'][0]['data']
                if qr_data:
                    qr_data_list.append(qr_data)
            except:
                pass

    document.close()
    return qr_data_list

# --- Infosys Processing ---
def process_infosys(qr_data, pdf_text, pdf_path, processed_names, fake_files_dict):
    try:
        qr_json = json.loads(qr_data)
        issued_to = qr_json.get("credentialSubject", {}).get("issuedTo", None)
        filename = os.path.basename(pdf_path)

        if issued_to and issued_to.lower() in pdf_text.lower():
            extracted_name = issued_to
            if extracted_name and extracted_name.lower() not in processed_names:
                destination_dir = ORIGINAL_DIR
                with file_move_lock:
                    shutil.move(pdf_path, os.path.join(destination_dir, filename))
                processed_names.add(extracted_name.lower())
                return {
                    "status": "Infosys Verified",
                    "file": filename,
                    "stored_in": destination_dir,
                    "issued_to": extracted_name
                }
            else:
                return {
                    "status": f"Duplicate Original: {extracted_name}",
                    "file": pdf_path
                }

        else:
            destination_dir = FAKE_DIR
            with file_move_lock:
                shutil.move(pdf_path, os.path.join(destination_dir, filename))
            if issued_to:
                fake_files_dict[filename] = issued_to  # Store file name and issued to name
            return {
                "status": "Infosys Fake",
                "file": filename,
                "stored_in": destination_dir,
                "issued_to": issued_to
            }

    except json.JSONDecodeError:
        return None

# --- Main Processing Function ---
def process_pdf_file(pdf_path, processed_names, fake_files_dict):
    qr_data_list = extract_qr_from_pdf(pdf_path)
    pdf_text = extract_text_from_pdf(pdf_path)

    if not qr_data_list:
        return {"status": "No QR codes found", "file": pdf_path}

    for qr_data in qr_data_list:
        if qr_data.startswith("{"):
            result = process_infosys(qr_data, pdf_text, pdf_path, processed_names, fake_files_dict)
            return result

    return {"status": "QR not recognized", "file": pdf_path}

# --- Helper Function for Parallel PDF Processing ---
def process_single_pdf(pdf_file, processed_names, fake_files_dict):
    filename = pdf_file.name
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb+") as destination:
        for chunk in pdf_file.chunks():
            destination.write(chunk)

    return process_pdf_file(file_path, processed_names, fake_files_dict)

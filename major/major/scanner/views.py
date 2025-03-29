from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .utils import process_single_pdf
from concurrent.futures import ThreadPoolExecutor
import os

UPLOAD_DIR = "media/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@csrf_exempt
def upload_folder(request):
    if request.method == "POST":
        processed_names = set()
        fake_files_dict = {}

        if "folder" not in request.FILES:
            return JsonResponse({"error": "No folder uploaded"}, status=400)

        folder = request.FILES.getlist("folder")
        results = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for pdf_file in folder:
                if not pdf_file.name.lower().endswith(".pdf"):
                    continue
                futures.append(executor.submit(process_single_pdf, pdf_file, processed_names, fake_files_dict))

            results = [future.result() for future in futures]

        return JsonResponse({
            "results": results,
            "original_names": list(processed_names),
            "fake_files": fake_files_dict
        }, status=200)

    return JsonResponse({"error": "Invalid request"}, status=400)

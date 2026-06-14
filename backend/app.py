from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .ocr_engine import MangaOCREngine

ocr_engine = MangaOCREngine(use_gpu=False)

app = FastAPI(title="MangaTleX", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/extract_text")
async def extract_text(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        result = ocr_engine.process_image(contents)
        return JSONResponse(result)
    
    except Exception as e:
        return JSONResponse({
            "success": False, "error": f"Failed to process image: {str(e)}"
        }, status_code=500)
    

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "MangaTleX",
        "easyocr_ready": ocr_engine.reader is not None,
        "tesseract_available": ocr_engine.tessearact_available
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting MangaTleX OCR API...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
import cv2
import numpy as np
import easyocr
import pytesseract
import re
import base64
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class TextLine:
    text: str
    confidence: float
    bbox: List[List[int]]
    position_y: int
    position_x: int

class MangaOCREngine:
    def __init__(self, use_gpu: bool = False):
        print("Initializing OCR engine...")
        self.render = easyocr.Reader(['en'], gpu=use_gpu)
        self.tessearact_available = self._check_tesseract()
        print("OCR engine initialized.")

    def _check_tesseract(self) -> bool:
        try:
            pytesseract.get_tesseract_version()
            return True
        except:
            return False

    def preprocess_image(self,image_bytes: bytes) -> Tuple[np.ndarray, np.ndarray]:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Could not decode image from bytes.")

        img = cv2.resize(img, None, fx=2, fy=2,
    interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, None, 15, 7, 21)
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + 
    cv2.THRESH_OTSU)
        
        white_pixels = cv2.countNonZero(binary)
        total_pixels = binary.shape[0] * binary.shape[1]
        if white_pixels > total_pixels * 0.7:
            binary = cv2.bitwise_not(binary)

        return img, binary
    
    def detect_text_regions(self, image: np.ndarray) -> List[Dict]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        edges = cv2.Canny(gray, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        dialeted = cv2.dilate(edges, kernel, iterations=2)
        contours, _ = cv2.findContours(dialeted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > 50 and h > 20 and w < image.shape[1] * 0.9 and h < image.shape[0] * 0.9:
                regions.append({
                    "x": int(x), "y": int(y),
                    "width": int(w), "height": int(h),
                    "area": int(w * h)
                })

        regions.sort(key=lambda r: (r["y"], r["x"]))
        return regions
    
    def extract_with_easyocr(self, image: np.ndarray) -> List[TextLine]:
        results = self.render.readtext(image, detail=1, paragraph=False)
        lines = []

        for (bbox, text, prob) in results:
            if prob > 0.25 and len(text.strip()) > 1:
                center_y = (bbox[0][1] + bbox[2][1]) // 2
                center_x = (bbox[0][0] + bbox[2][0]) // 2

                lines.append(TextLine(
                    text=text.strip(),
                    confidence=round(float(prob), 3),
                    bbox = [[int(p[0]), int(p[1])] for p in bbox],
                    position_y=int(center_y),
                    position_x=int(center_x)
                ))

        return lines
    
    def extract_with_tesseract(self, image: np.ndarray) -> List[TextLine]:
        if not self.tessearact_available:
            return []
        
        data = pytesseract.image_to_data(
            image,
            lang='eng',
            config='--psm 6',
            output_type=pytesseract.Output.DICT
        )

        lines = []
        n_boxes = len(data['text'])

        for i in range(n_boxes):
            text = data['text'][i].strip()
            conf = int (data['conf'][i])

            if conf > 30 and len(text) > 1:
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                bbox = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]

                lines.append(TextLine(
                    text=text,
                    confidence=conf / 100.0,
                    bbox=bbox,
                    postiion_y=y,
                    position_x=x
                ))
        
        return lines
    
    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        
        text = re.sub(r'\s+', ' ', text)

        replacements = {
            '|': 'I',
            '0': 'O',
            '1': 'l',
            '@': 'a',
            '$': 'S',
        }

        for wrong, correct in replacements.items():
            text = text.replace(wrong, correct)

        if len(text) == 1 and text not in 'AIaiOo':
            return ""
        
        return text.strip()
    
    def process_image(self, image_bytes: bytes) -> Dict:
        try:
            original, processed = self.preprocess_image(image_bytes)
            regions = self.detect_text_regions(original)

            lines = self.extract_with_easyocr(original)
            engine_used = "easyocr"

            if not lines and self.tessearact_available:
                lines = self.extract_with_tesseract(original)
                engine_used = "tesseract"

            lines.sort(key=lambda x: (x.position_y, x.position_x))

            cleaned_lines = []
            seen_texts = set()

            for line in lines:
                clean = self.clean_text(line.text)
                if clean and clean not in seen_texts:
                    seen_texts.add(clean)
                    cleaned_lines.append({
                        "text": clean,
                        "confidence": line.confidence,
                        "bbox": line.bbox
                    })
            
            full_text = "\n".join([line["text"] for l in cleaned_lines])
            preview = self._generate_preview(original, cleaned_lines)

            return {
                "success": True,
                "text": full_text,
                "lines": cleaned_lines,
                "regions_count": len(regions),
                "preview": preview,
                "engine": engine_used
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_preview(self, image: np.ndarray, lines: List[Dict]) -> str:

        preview = image.copy()
        scale = 0.5
        preview = cv2.resize(preview, None, fx=scale, fy=scale)

        for i, line in enumerate(lines):
            scaled_bbox = [[int(p[0] * scale), int(p[1] * scale)] for p in line["bbox"]]
            pts = np.array(scaled_bbox, np.int32)
            pts = pts.reshape((-1, 1, 2))
            cv2.polylines(preview, [pts], True, (0, 255, 0), 2)

            x, y = scaled_bbox[0]
            cv2.putText(
                preview,
                str(i + 1),
                (int(x), int(y) - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

        _, buffer = cv2.imencode('.png', preview)
        preview_b64 = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/png;base64,{preview_b64}"
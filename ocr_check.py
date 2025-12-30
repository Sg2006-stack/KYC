import cv2
import pytesseract
from PIL import Image
import re
# Set Tesseract path (Windows only)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# image_path = r"C:\Users\Arnab\OneDrive\Desktop\code\pythonprojects\KYC\uploads\aadhaar\a653a7cc-6021-4319-b299-9580c2f11126.jpg"
def extract_text(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return ""

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    text = pytesseract.image_to_string(gray)
    # if result is empty or too short, try additional preprocessing
    if len(re.sub(r'\s+', '', text)) < 3:
        # upscale
        h, w = gray.shape[:2]
        scale = 2
        large = cv2.resize(gray, (w*scale, h*scale), interpolation=cv2.INTER_CUBIC)
        # denoise and sharpen
        large = cv2.bilateralFilter(large, 9, 75, 75)
        # adaptive threshold
        th = cv2.adaptiveThreshold(large, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)

        # try with whitelist (PAN is alphanumeric uppercase)
        config = '--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        text2 = pytesseract.image_to_string(th, config=config)
        if len(re.sub(r'\s+', '', text2)) >= 3:
            return text2

        # fallback: try simple resizing and psm 7
        text3 = pytesseract.image_to_string(large, config='--psm 7')
        if len(re.sub(r'\s+', '', text3)) >= 3:
            return text3

    return text



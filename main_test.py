from ocr_check import extract_text
from aadhar_validation import extract_aadhaar_number, extract_dob, is_age_above_18
from pan_validation import extract_pan_number,is_valid_pan
from face_match_selfie import match_faces
# Path to uploaded Aadhaar image
image_path = r"C:\Users\Arnab\OneDrive\Desktop\code\pythonprojects\KYC\uploads\aadhaar\a653a7cc-6021-4319-b299-9580c2f11126.jpg"
pan_path= r"C:\Users\Arnab\OneDrive\Desktop\code\pythonprojects\KYC\uploads\pan\d4552e6d-dcc5-48eb-9e08-93dd5b1071b2.jpeg"
selfie_img = r"C:\Users\Arnab\OneDrive\Desktop\code\pythonprojects\KYC\uploads\selfie\ca53cd33-cfae-4ae0-b06e-c8a3912db502.png"
# Step 1: OCR
text = extract_text(image_path)
print("OCR TEXT:\n", text)

# Step 2: Validation
aadhaar_no = extract_aadhaar_number(text)
dob = extract_dob(text)
adult = is_age_above_18(dob)

print("\nEXTRACTED DATA:")
print("Aadhaar Number:", aadhaar_no)
print("DOB:", dob)
print("Age >= 18:", adult)

# pan validation
pan_text = extract_text(pan_path)
print("\npan text:\n", pan_text)

pan_number = extract_pan_number(pan_text)
valid_pan = is_valid_pan(pan_number)

print("\n🔍 PAN DETAILS EXTRACTED:")
print("PAN Number:", pan_number)
print("PAN Format Valid:", valid_pan)

# selfie_verification

print("\n face detection")
result = match_faces(pan_path , selfie_img)
print(result)

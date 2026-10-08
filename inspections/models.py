from django.db import models
from django.conf import settings


# ============================= INSPECTION MODELS =============================
class Inspection(models.Model):

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        IMAGE_CAPTURE = 'IMAGE_CAPTURE', 'Image Capture'
        OCR_PROCESSING  = 'OCR_PROCESSING', 'OCR Processing '
        AI_PROCESSING = 'AI_PROCESSING', 'AI Processing'
        VERIFICATION_PENDING = 'VERIFICATION_PENDING', 'Verification Pending'
        VERFIED = 'VERIFIED', 'Verified'
        EVALUATING = 'EVALUATING','Evaluating'
        COMPLETED = 'COMPLETED', 'Completed' 
        FAILED = 'FAILED', 'Failed'

    inspection_number = models.CharField( max_length = 30, unique = True )
    inspector = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete = models.PROTECT, related_name = 'inspections')
    product = models.ForeignKey( 'products.Product', on_delete=models.PROTECT, related_name = 'inspections' )
    status = models.CharField( max_length=30, choices=Status.choices, default=Status.DRAFT)
    remarks = models.TextField( blank = True, null = True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.inspection_number

# =========================== INSPECTION IMAGE MODEL ===========================
class InspectionImage(models.Model):

    class ImageType(models.TextChoices):
        FRONT = 'FRONT', 'Front'
        BACK = 'BACK', 'Back'
        SIDE = 'SIDE', 'Side'
        INGREDIENTS = 'INGREDIENTS', 'Ingredients'
        NUTRITION = 'NUTRITION', 'Nutrition'
        OTHER = 'OTHER', 'Other'

    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name = 'images')
    image = models.ImageField(upload_to='inspections/%Y/%m/%d/')
    image_type = models.CharField(max_length=20, choices=ImageType.choices, default=ImageType.OTHER)
    sequence = models.PositiveIntegerField(default=1)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return  f"{self.inspection.inspection_number} - {self.image_type}"

# ========================== OCR RESULT MODEL ==========================
class OCRResult(models.Model):

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    inspection_image = models.OneToOneField(InspectionImage, on_delete=models.CASCADE, related_name = 'ocr_result')
    raw_text = models.TextField(blank=True)
    confidence = models.FloatField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"OCR - {self.inspection_image}"

# =============================== AI ANALYSIS ================================
class AIAnalysis(models.Model):

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMOLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name='ai_analyses')
    structured_data = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"AI Analysis - {self.inspection.inspection_number}"

# ========================= VERIFIED INSPECTION DATA =========================
class VerifiedInspectionData(models.Model):

    inspection = models.OneToOneField(Inspection, on_delete=models.CASCADE, related_name='verified_data')
    product_name = models.CharField(max_length=255, blank=True)
    brand = models.CharField(max_length=255, blank=True)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    net_quantity = models.CharField(max_length=100, blank=True)
    manufacturing_date = models.CharField(max_length=100, blank=True)
    best_before = models.CharField(max_length=100, blank=True)
    expiry_date = models.CharField(max_length=100, blank=True)
    ingredients = models.CharField(max_length=100, blank=True)
    fssai_license = models.CharField(max_length=100, blank=True)
    manufacturer = models.TextField(max_length=100, blank=True)
    packer = models.TextField(blank=True)
    importer = models.TextField(blank=True)
    other_declarations = models.TextField(blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='verified_inspections')
    verified_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Verified Data - {self.inspection.inspection_number}"
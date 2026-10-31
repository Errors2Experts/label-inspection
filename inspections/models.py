
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


# ============================= INSPECTION MODEL =============================

class Inspection(models.Model):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IMAGE_CAPTURE = "IMAGE_CAPTURE", "Image Capture"
        OCR_PROCESSING = "OCR_PROCESSING", "OCR Processing"
        OCR_COMPLETED = "OCR_COMPLETED", "OCR Completed"
        AI_PROCESSING = "AI_PROCESSING", "AI Processing"
        VERIFICATION_PENDING = "VERIFICATION_PENDING", "Verification Pending"
        VERIFIED = "VERIFIED", "Verified"
        EVALUATING = "EVALUATING", "Evaluating"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    inspection_number = models.CharField(
        max_length=30,
        unique=True,
    )

    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inspections",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="inspections",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    remarks = models.TextField(blank=True, null=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Inspection"
        verbose_name_plural = "Inspections"

    def __str__(self):
        return self.inspection_number


# =========================== INSPECTION IMAGE MODEL ===========================

class InspectionImage(models.Model):

    class ImageType(models.TextChoices):
        FRONT = "FRONT", "Front"
        BACK = "BACK", "Back"
        SIDE = "SIDE", "Side"
        INGREDIENTS = "INGREDIENTS", "Ingredients"
        NUTRITION = "NUTRITION", "Nutrition"
        OTHER = "OTHER", "Other"

    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ImageField(
        upload_to="inspections/%Y/%m/%d/",
    )

    image_type = models.CharField(
        max_length=20,
        choices=ImageType.choices,
        default=ImageType.OTHER,
    )

    sequence = models.PositiveIntegerField(default=1)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence", "uploaded_at"]
        verbose_name = "Inspection Image"
        verbose_name_plural = "Inspection Images"
        constraints = [
            models.UniqueConstraint(
                fields=["inspection", "sequence"],
                name="unique_inspection_image_sequence",
            )
        ]

    def __str__(self):
        return (
            f"{self.inspection.inspection_number} - "
            f"{self.image_type} - Image {self.sequence}"
        )


# ================================ OCR RESULT MODEL ================================

class OCRResult(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    inspection_image = models.OneToOneField(
        InspectionImage,
        on_delete=models.CASCADE,
        related_name="ocr_result",
    )

    raw_text = models.TextField(blank=True)

    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"OCR - {self.inspection_image}"


# ================================ AI ANALYSIS MODEL ================================

class AIAnalysis(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.CASCADE,
        related_name="ai_analyses",
    )

    structured_data = models.JSONField(default=dict, blank=True)

    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"AI Analysis - {self.inspection.inspection_number}"


# ========================= VERIFIED INSPECTION DATA MODEL =========================

class VerifiedInspectionData(models.Model):

    inspection = models.OneToOneField(
        Inspection,
        on_delete=models.CASCADE,
        related_name="verified_data",
    )

    product_name = models.CharField(max_length=255, blank=True)
    brand = models.CharField(max_length=255, blank=True)

    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    net_quantity = models.CharField(max_length=100, blank=True)
    manufacturing_date = models.CharField(max_length=100, blank=True)
    best_before = models.CharField(max_length=100, blank=True)
    expiry_date = models.CharField(max_length=100, blank=True)
    ingredients = models.TextField(blank=True)
    fssai_license = models.CharField(max_length=100, blank=True)
    manufacturer = models.TextField(blank=True)
    packer = models.TextField(blank=True)
    importer = models.TextField(blank=True)
    other_declarations = models.TextField(blank=True)

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verified_inspections",
    )

    verified_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Verified Data - {self.inspection.inspection_number}"

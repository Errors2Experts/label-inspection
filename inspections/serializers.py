import uuid
from .models import *
from django.utils import timezone
from rest_framework import serializers

# ================================= OCR RESULT SERIALIZER =================================

class OCRResultSerializer(serializers.ModelSerializer):

    class Meta:
        model = OCRResult
        fields = [
            'id',
            'inspection_image',
            'raw_text',
            'confidence',
            'status',
            'error_message',
            'processed_at'
        ]
        read_only_fields = fields

# ================================= INSPECTION IMAGE SERIALIZER =================================

class InspectionImageSerializer(serializers.ModelSerializer):

    ocr_result = OCRResultSerializer(read_only=True)

    class Meta:
        model = InspectionImage
        fields = [
            'id',
            'inspection',
            'image',
            'image_type',
            'sequence',
            'uploaded_at',
            'ocr_result',
        ]
        read_only_fields = [
            'id',
            'inspection',
            'sequence',
            'uploaded_at',
            'ocr_result',
        ]

    def validate_image(self, value):
        max_size = 10 * 1024 * 1024  # 10 MB

        if value.size > max_size:
            raise serializers.ValidationError(
                'Image size must not exceed 10 MB.'
            )

        return value

# ================================= AI ANALYSIS SERIALIZER ==================================

class AIAnalysisSerializer(serializers.ModelSerializer):

    class Meta:
        model = AIAnalysis
        fields = [
            'id',
            'inspection',
            'structured_data',
            'confidence',
            'status',
            'error_message',
            'processed_at',
        ]
        read_only_fields = fields

# ================================= VERIFIED DATA SERIALIZER =================================

class VerifiedDataSerializer(serializers.ModelSerializer):

    class Meta:
        model = VerifiedInspectionData
        fields = [
            'id',
            'inspection',
            'product_name',
            'brand',
            'mrp',
            'net_quantity',
            'manufacturing_date',
            'best_before',
            'expiry_date',
            'ingredients',
            'fssai_license',
            'manufacturer',
            'packer',
            'importer',
            'other_declarations',
            'verified_by',
            'verified_at',
            'is_verified',
        ]
        read_only_fields = [
            'id',
            'inspection',
            'verified_by',
            'verified_at',
            'is_verified',
        ]
    def validate_mrp(self, value):

        if value is not None and value < 0:
            raise serializers.ValidationError(
                'MRP cannot be negative.'
            )
        return value

# ==================================== INSPECTION SERIALIZER ====================================

class InspectionSerializer(serializers.ModelSerializer):
    images = InspectionImageSerializer(many=True, read_only=True)
    ai_analyses = AIAnalysisSerializer(many = True, read_only = True)
    verified_data = VerifiedDataSerializer(read_only = True)

    class Meta:
        model = Inspection
        fields = [
            'id',
            'inspection_number',
            'inspector',
            'product',
            'status',
            'remarks',
            'started_at',
            'completed_at',
            'created_at',
            'updated_at',
            'images',
            'ai_analyses',
            'verified_data',
        ]
        read_only_fields = [
            'id',
            'inspection_number',
            'inspector',
            'status',
            'started_at',
            'completed_at',
            'created_at',
            'updated_at',
            'images',
            'ai_analyses',
            'verified_data',
        ]

    def create(self, validated_data):
        timestamp = timezone.now().strftime('%Y%m%d')
        inspection_number = (
            f"INSP-{timestamp}-{uuid.uuid4().hex[:8].upper()}"
        )

        validated_data["inspection_number"] = inspection_number

        return super().create(validated_data)

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)

        if instance is None and not attrs.get("product"):
            raise serializers.ValidationError({
                'Product': 'A product must be associated with the inspection.'
            })
        return attrs
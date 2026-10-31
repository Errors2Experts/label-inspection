import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import *
from .serializers import *
from .ocr_service import extract_text
from .ai_service import extract_label_data

logger = logging.getLogger(__name__)



from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import parser_classes

# This is for postman testing remove after the testing
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def test_ocr(request):
    image = request.FILES.get("image")

    if not image:
        return Response(
            {"detail": "Upload an image using the 'image' field."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if image.size > 10 * 1024 * 1024:
        return Response(
            {"detail": "Image size must not exceed 10 MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = extract_text(image)

        return Response({
            "raw_text": result["raw_text"],
            "confidence": result["confidence"],
        })

    except Exception:
        logger.exception("Temporary OCR test failed")
        return Response(
            {"detail": "OCR processing failed. Check server logs."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

# This is for postman testing remove after the testing
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def test_ai_extraction(request):
    image = request.FILES.get("image")

    if not image:
        return Response(
            {"detail": "Upload an image using the 'image' field."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if image.size > 10 * 1024 * 1024:
        return Response(
            {"detail": "Image size must not exceed 10 MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Step 1: Extract text from the uploaded image.
    try:
        ocr_result = extract_text(image)
        raw_text = ocr_result["raw_text"].strip()

        if not raw_text:
            return Response(
                {"detail": "OCR did not extract any text."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except Exception:
        logger.exception("AI test: OCR failed")
        return Response(
            {"detail": "OCR processing failed. Check server logs."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Step 2: Pass OCR text to the existing Gemini extraction service.
    try:
        structured_data = extract_label_data(raw_text)

        return Response(
            {
                "raw_text": raw_text,
                "ocr_confidence": ocr_result["confidence"],
                "structured_data": structured_data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as exc:
        logger.exception("Standalone AI extraction test failed")

        return Response(
            {
                "detail": "AI extraction failed.",
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

class InspectionViewSet(viewsets.ModelViewSet):
    """
    Handles inspection CRUD operations and related workflow APIs.
    """

    serializer_class = InspectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Inspection.objects
            .filter(inspector=self.request.user)
            .select_related("product", "inspector")
            .prefetch_related("images", "ai_analyses")
        )

    def perform_create(self, serializer):
        serializer.save(inspector=self.request.user)

    # ======================== INSPECTION IMAGES ========================

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="images",
    )
    def images(self, request, pk=None):
        inspection = self.get_object()

        if request.method == "GET":
            images = inspection.images.all()

            serializer = InspectionImageSerializer(
                images,
                many=True,
                context={"request": request},
            )

            return Response(serializer.data)

        serializer = InspectionImageSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            last_sequence = (
                InspectionImage.objects
                .filter(inspection=inspection)
                .order_by("-sequence")
                .values_list("sequence", flat=True)
                .first()
            )

            next_sequence = (last_sequence or 0) + 1

            image = serializer.save(
                inspection=inspection,
                sequence=next_sequence,
            )

            if inspection.status == Inspection.Status.DRAFT:
                inspection.status = Inspection.Status.IMAGE_CAPTURE
                inspection.save(
                    update_fields=["status", "updated_at"]
                )

        return Response(
            InspectionImageSerializer(
                image,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    # ============================ OCR ============================
    
    @action(
        detail=True,
        methods=["get", "post"],
        url_path="ocr",
    )
    def ocr(self, request, pk=None):
        inspection = self.get_object()

        # GET: Return OCR results already stored in the database.
        if request.method == "GET":
            results = OCRResult.objects.filter(
                inspection_image__inspection=inspection
            ).select_related("inspection_image")

            serializer = OCRResultSerializer(
                results,
                many=True,
            )

            return Response(serializer.data)

        # POST: Actually process the uploaded images.
        images = list(inspection.images.all())

        if not images:
            return Response(
                {
                    "detail": (
                        "Upload at least one inspection image "
                        "before starting OCR."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        inspection.status = Inspection.Status.OCR_PROCESSING
        inspection.save(update_fields=["status", "updated_at"])

        results = []
        succeeded = 0
        failed = 0

        for image in images:
            # One OCRResult per image, as defined by your model.
            ocr_result, _ = OCRResult.objects.get_or_create(
                inspection_image=image,
            )

            ocr_result.status = OCRResult.Status.PROCESSING
            ocr_result.error_message = ""
            ocr_result.processed_at = None
            ocr_result.save(
                update_fields=[
                    "status",
                    "error_message",
                    "processed_at",
                ]
            )

            try:
                extraction = extract_text(image.image)

                ocr_result.raw_text = extraction["raw_text"]
                ocr_result.confidence = extraction["confidence"]
                ocr_result.status = OCRResult.Status.COMPLETED
                ocr_result.error_message = ""
                ocr_result.processed_at = timezone.now()

                ocr_result.save(
                    update_fields=[
                        "raw_text",
                        "confidence",
                        "status",
                        "error_message",
                        "processed_at",
                    ]
                )

                succeeded += 1

            except Exception:
                # Keep technical details in server logs rather than
                # returning internal errors to the API caller.
                logger.exception(
                    "OCR failed for inspection %s, image %s",
                    inspection.inspection_number,
                    image.pk,
                )

                ocr_result.status = OCRResult.Status.FAILED
                ocr_result.error_message = (
                    "OCR processing failed. Check server logs."
                )
                ocr_result.processed_at = timezone.now()

                ocr_result.save(
                    update_fields=[
                        "status",
                        "error_message",
                        "processed_at",
                    ]
                )

                failed += 1

            results.append(ocr_result)

        # Mark the stage as completed only if every image succeeds.
        inspection.status = (
            Inspection.Status.OCR_COMPLETED
            if failed == 0
            else Inspection.Status.FAILED
        )
        inspection.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "detail": "OCR processing finished.",
                "inspection_number": inspection.inspection_number,
                "inspection_status": inspection.status,
                "total_images": len(images),
                "succeeded": succeeded,
                "failed": failed,
                "results": OCRResultSerializer(
                    results,
                    many=True,
                ).data,
            },
            status=status.HTTP_200_OK,
        )

 
    # ======================== AI ANALYSIS ========================

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="ai_analysis",
    )

    def ai_analysis(self, request, pk=None):
        inspection = self.get_object()

        if request.method == "GET":
            analysis = (
                AIAnalysis.objects
                .filter(inspection = inspection)
                .order_by("-id")
                .first()
            )

            if analysis is None:
                return Response(
                    {"detail": "No AI analysis exists for this inspection."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(AIAnalysisSerializer(analysis).data)

        # POST: Allow AI extraction only after OCR is completed,
        # or when retrying a failed inspection.
        if inspection.status not in [
            Inspection.Status.OCR_COMPLETED,
            Inspection.Status.FAILED,
        ]:
            return Response(
                {
                    "detail": (
                        "AI extraction is allowed only after OCR completion "
                        "or when retrying a failed inspection."
                    ),
                    "inspection_status": inspection.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # POST: Ensure the Gemini key is configured.
        if not settings.GEMINI_API_KEY:
            return Response(
                {"detail": "Gemini API key is not configured on the server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Use only successfully completed OCR results.
        ocr_results = (
            OCRResult.objects
            .filter(
                inspection_image__inspection = inspection,
                status = "COMPLETED",
            )
            .select_related("inspection_image")
            .order_by("inspection_image__sequence")
        )

        ocr_section = []

        for result in ocr_results:
            if result.raw_text and result.raw_text.strip():
                ocr_section.append(
                    f"Image sequence {result.inspection_image.sequence}:\n"
                    f"{result.raw_text.strip()}"
                )

        if not ocr_section:
            return Response(
                {
                    "detail": (
                        "No completed OCR text was found. "
                        "Run OCR successfully before AI extraction."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create a record so processing failures can also be tracked.
        analysis = AIAnalysis.objects.create(
            inspection = inspection,
            status = "PROCESSING",
            error_message = "",
        )

        inspection.status = "AI_PROCESSING"
        inspection.save(update_fields=["status", "updated_at"])

        try:
            combined_ocr_text = "\n\n".join(ocr_section)

            structured_data = extract_label_data(combined_ocr_text)

            analysis.structured_data = structured_data
            analysis.status = "COMPLETED"
            analysis.error_message = ""
            analysis.processed_at = timezone.now()
            analysis.save(
                update_fields=[
                    "structured_data",
                    "status",
                    "error_message",
                    "processed_at",
                ]
            )

            inspection.status = Inspection.Status.VERIFICATION_PENDING
            inspection.save(update_fields=["status", "updated_at"])

            return Response(
                AIAnalysisSerializer(analysis).data,
                status=status.HTTP_200_OK
            )

        except Exception as exe:
            logger.exception(
                "AI extraction failed for inspection %s",
                inspection.pk,
            )

            analysis.status = "FAILED"
            analysis.error_message = str(exe)[:2000]
            analysis.processed_at = timezone.now()
            analysis.save(
                update_fields=[
                    "status",
                    "error_message",
                    "processed_at",
                ]
            )

            inspection.status = Inspection.Status.FAILED
            inspection.save(update_fields=["status", "updated_at"])

            return Response (
                {
                    "detail": (
                        "AI extraction failed. Check the Django server logs "
                        "for the underlying error."
                    ),
                    "analysis_id": analysis.pk,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ====================== INSPECTOR VERIFICATION ======================

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="verify",
    )
    def verify(self, request, pk=None):
        inspection = self.get_object()

        # GET: Return AI-extracted fields for review and any
        # previously saved verified data.
        if request.method == "GET":
            analysis = (
                AIAnalysis.objects
                .filter(
                    inspection=inspection,
                    status=AIAnalysis.Status.COMPLETED,
                )
                .order_by("-processed_at", "-id")
                .first()
            )

            verified_data = (
                VerifiedInspectionData.objects
                .filter(inspection=inspection)
                .first()
            )

            return Response({
                "inspection_id": inspection.pk,
                "inspection_number": inspection.inspection_number,
                "inspection_status": inspection.status,
                "ai_analysis": (
                    AIAnalysisSerializer(analysis).data
                    if analysis else None
                ),
                "verified_data": (
                    VerifiedDataSerializer(verified_data).data
                    if verified_data else None
                ),
            })

        # POST: Verification requires a completed AI analysis.
        with transaction.atomic():
            # Lock the inspection while the verification is saved.
            inspection = (
                Inspection.objects
                .select_for_update()
                .get(pk=inspection.pk)
            )

            # Only allow the normal verification-pending state.
            if inspection.status != Inspection.Status.VERIFICATION_PENDING:
                return Response(
                    {
                        "detail": (
                            "This inspection is not awaiting verification."
                        ),
                        "inspection_status": inspection.status,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            analysis = (
                AIAnalysis.objects
                .filter(
                    inspection=inspection,
                    status=AIAnalysis.Status.COMPLETED,
                )
                .order_by("-processed_at", "-id")
                .first()
            )

            if analysis is None:
                return Response(
                    {
                        "detail": (
                            "A completed AI analysis is required "
                            "before inspector verification."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not isinstance(analysis.structured_data, dict):
                return Response(
                    {
                        "detail": (
                            "AI analysis data is invalid. "
                            "Run AI extraction again."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Prevent an empty submission from being marked verified.
            editable_fields = {
                "product_name",
                "brand",
                "mrp",
                "net_quantity",
                "manufacturing_date",
                "best_before",
                "expiry_date",
                "ingredients",
                "fssai_license",
                "manufacturer",
                "packer",
                "importer",
                "other_declarations",
            }

            submitted_fields = editable_fields.intersection(
                request.data.keys()
            )

            if not submitted_fields:
                return Response(
                    {
                        "detail": (
                            "Submit at least one reviewed label field."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            verified_data = (
                VerifiedInspectionData.objects
                .filter(inspection=inspection)
                .first()
            )

            if verified_data and verified_data.is_verified:
                return Response(
                    {
                        "detail": (
                            "This inspection has already been verified."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            serializer = VerifiedDataSerializer(
                instance=verified_data,
                data=request.data,
                partial=verified_data is not None,
                context={"request": request},
            )

            serializer.is_valid(raise_exception=True)

            verified_data = serializer.save(
                inspection=inspection,
                verified_by=request.user,
                verified_at=timezone.now(),
                is_verified=True,
            )

            inspection.status = Inspection.Status.VERIFIED
            inspection.save(
                update_fields=["status", "updated_at"]
            )

        return Response(
            {
                "detail": "Inspector verification completed successfully.",
                "inspection_status": inspection.status,
                "verified_data": VerifiedDataSerializer(
                    verified_data
                ).data,
            },
            status=(
                status.HTTP_200_OK
                if verified_data
                else status.HTTP_201_CREATED
            ),
        )
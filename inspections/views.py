from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import *
from .serializers import *

import logging

from .ocr_service import extract_text

logger = logging.getLogger(__name__)


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
        url_path="ai-analysis",
    )
    def ai_analysis(self, request, pk=None):
        inspection = self.get_object()

        if request.method == "GET":
            analyses = inspection.ai_analyses.all()

            serializer = AIAnalysisSerializer(
                analyses,
                many=True,
            )

            return Response(serializer.data)

        if not inspection.images.exists():
            return Response(
                {
                    "detail": (
                        "Upload inspection images "
                        "before preparing AI analysis."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            analysis = (
                inspection.ai_analyses
                .filter(status=AIAnalysis.Status.PENDING)
                .first()
            )

            if analysis is None:
                analysis = AIAnalysis.objects.create(
                    inspection=inspection,
                    status=AIAnalysis.Status.PENDING,
                )

        return Response(
            {
                "detail": (
                    "AI analysis record is ready. "
                    "The AI engine is not connected yet."
                ),
                "analysis": AIAnalysisSerializer(
                    analysis
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    # ====================== VERIFIED INSPECTION DATA ======================

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="verify",
    )
    def verify(self, request, pk=None):
        inspection = self.get_object()

        if request.method == "GET":
            verified_data = get_object_or_404(
                VerifiedInspectionData,
                inspection=inspection,
            )

            serializer = VerifiedDataSerializer(
                verified_data
            )

            return Response(serializer.data)

        with transaction.atomic():
            verified_data = (
                VerifiedInspectionData.objects
                .filter(inspection=inspection)
                .first()
            )

            is_update = verified_data is not None

            serializer = VerifiedDataSerializer(
                instance=verified_data,
                data=request.data,
                partial=is_update,
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

        response_status = (
            status.HTTP_200_OK
            if is_update
            else status.HTTP_201_CREATED
        )

        return Response(
            {
                "detail": (
                    "Verified inspection data saved successfully."
                ),
                "verified_data": VerifiedDataSerializer(
                    verified_data
                ).data,
            },
            status=response_status,
        )
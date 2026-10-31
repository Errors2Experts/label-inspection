
"use strict";
/* =========================================================
   LABEL INSPECTION
   Django REST Framework integration
========================================================= */

(() => {
    // -----------------------------------------------------
    // API CONFIGURATION
    // -----------------------------------------------------

    const API_BASE = "/api/inspections/inspections/";

    const MAX_IMAGE_SIZE = 10 * 1024 * 1024;

    const ALLOWED_IMAGE_TYPES = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/bmp",
        "image/tiff"
    ];

    // -----------------------------------------------------
    // DOM ELEMENTS
    // -----------------------------------------------------

    const $ = (selector) => document.querySelector(selector);

    const $$ = (selector) => [...document.querySelectorAll(selector)];

    const elements = {
        notice: $("#notice"),

        productId: $("#productId"),
        imageOnly: $("#imageOnly"),
        createInspection: $("#createInspection"),

        imageInspectionNumber: $("#imageInspectionNumber"),
        imageProductName: $("#imageProductName"),

        images: $("#images"),
        uploadArea: $("#uploadArea"),
        imagePreview: $("#imagePreview"),
        imageSelectionInfo: $("#imageSelectionInfo"),
        uploadImages: $("#uploadImages"),

        extractInspectionNumber: $("#extractInspectionNumber"),
        extractImageCount: $("#extractImageCount"),

        ocrStatus: $("#ocrStatus"),
        aiStatus: $("#aiStatus"),
        extractionOutput: $("#extractionOutput"),

        runExtraction: $("#runExtraction"),
        openVerification: $("#openVerification"),

        verifyInspectionNumber: $("#verifyInspectionNumber"),
        verificationStatus: $("#verificationStatus"),
        verificationFields: $("#verificationFields"),
        verificationForm: $("#verificationForm"),
        confirmVerification: $("#confirmVerification"),
        inspectorRemarks: $("#inspectorRemarks"),
        submitVerification: $("#submitVerification"),

        resultHeading: $("#resultHeading"),
        resultDescription: $("#resultDescription"),
        resultInspectionNumber: $("#resultInspectionNumber"),
        resultInspectionStatus: $("#resultInspectionStatus"),
        resultImageCount: $("#resultImageCount"),
        resultOutput: $("#resultOutput"),
        finishInspection: $("#finishInspection")
    };

    // -----------------------------------------------------
    // WORKFLOW STATE
    // -----------------------------------------------------

    const state = {
        currentStep: 1,
        inspectionId: null,
        inspectionNumber: null,
        inspectionStatus: null,
        productId: null,
        productName: "Image-only inspection",
        uploadedImages: [],
        aiData: {},
        verifiedData: null,
        extractionCompleted: false,
        verificationCompleted: false,
        busy: false
    };

    // -----------------------------------------------------
    // INSPECTOR VERIFICATION FIELDS
    // Must match VerifiedInspectionData model fields.
    // -----------------------------------------------------

    const FIELD_DEFINITIONS = [
        {
            name: "product_name",
            label: "Product Name",
            type: "text"
        },
        {
            name: "brand",
            label: "Brand",
            type: "text"
        },
        {
            name: "mrp",
            label: "Maximum Retail Price (MRP)",
            type: "text"
        },
        {
            name: "net_quantity",
            label: "Net Quantity",
            type: "text"
        },
        {
            name: "manufacturing_date",
            label: "Manufacturing Date",
            type: "text"
        },
        {
            name: "best_before",
            label: "Best Before",
            type: "text"
        },
        {
            name: "expiry_date",
            label: "Expiry Date",
            type: "text"
        },
        {
            name: "ingredients",
            label: "Ingredients",
            type: "textarea"
        },
        {
            name: "fssai_license",
            label: "FSSAI License Number",
            type: "text"
        },
        {
            name: "manufacturer",
            label: "Manufacturer",
            type: "textarea"
        },
        {
            name: "packer",
            label: "Packer",
            type: "textarea"
        },
        {
            name: "importer",
            label: "Importer",
            type: "textarea"
        },
        {
            name: "other_declarations",
            label: "Other Declarations",
            type: "textarea"
        }
    ];

    // -----------------------------------------------------
    // NOTIFICATIONS
    // -----------------------------------------------------

    function showNotice(message, type = "info") {
        if (!elements.notice) return;

        elements.notice.textContent = message;
        elements.notice.hidden = false;

        elements.notice.classList.remove(
            "notice-success",
            "notice-error",
            "notice-info"
        );

        elements.notice.classList.add(`notice-${type}`);

        elements.notice.scrollIntoView({
            behavior: "smooth",
            block: "nearest"
        });
    }

    function hideNotice() {
        if (elements.notice) {
            elements.notice.hidden = true;
        }
    }

    function showError(message) {
        showNotice(message, "error");
    }

    function showSuccess(message) {
        showNotice(message, "success");
    }

    // -----------------------------------------------------
    // DJANGO CSRF SUPPORT
    // Uses Django session authentication on the same origin.
    // -----------------------------------------------------

    function getCookie(name) {
        const prefix = `${name}=`;

        const cookies = document.cookie.split(";");

        for (const cookie of cookies) {
            const trimmed = cookie.trim();

            if (trimmed.startsWith(prefix)) {
                return decodeURIComponent(
                    trimmed.substring(prefix.length)
                );
            }
        }

        return "";
    }

    function getCsrfToken() {
        return (
            getCookie("csrftoken") ||
            document.querySelector('meta[name="csrf-token"]')?.content ||
            document.querySelector(
                'input[name="csrfmiddlewaretoken"]'
            )?.value ||
            ""
        );
    }

    // -----------------------------------------------------
    // API REQUEST HELPER
    // -----------------------------------------------------

    async function apiRequest(path, options = {}) {
        const headers = new Headers(options.headers || {});

        headers.set("Accept", "application/json");

        const method = (options.method || "GET").toUpperCase();

        if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
            const csrfToken = getCsrfToken();

            if (csrfToken) {
                headers.set("X-CSRFToken", csrfToken);
            }
        }

        if (
            options.body &&
            !(options.body instanceof FormData) &&
            typeof options.body === "string"
        ) {
            headers.set("Content-Type", "application/json");
        }

        const response = await fetch(path, {
            ...options,
            method,
            headers,
            credentials: "same-origin"
        });

        const contentType =
            response.headers.get("content-type") || "";

        let data;

        if (contentType.includes("application/json")) {
            data = await response.json();
        } else {
            const text = await response.text();

            data = {
                detail: text.startsWith("<!DOCTYPE") ||
                    text.startsWith("<html")
                    ? "The server returned an HTML page instead of JSON. Check your login session and API URL."
                    : text || "The server returned an empty response."
            };
        }

        if (!response.ok) {
            const message = formatApiError(data, response.status);

            const error = new Error(message);
            error.status = response.status;
            error.data = data;

            throw error;
        }

        return data;
    }

    function formatApiError(data, statusCode) {
        if (data && typeof data.detail === "string") {
            return data.detail;
        }

        if (data && typeof data === "object") {
            const messages = [];

            for (const [field, errors] of Object.entries(data)) {
                const value = Array.isArray(errors)
                    ? errors.join(", ")
                    : typeof errors === "object"
                        ? JSON.stringify(errors)
                        : String(errors);

                messages.push(`${field}: ${value}`);
            }

            if (messages.length) {
                return messages.join("\n");
            }
        }

        return `Request failed with status ${statusCode}.`;
    }

    // -----------------------------------------------------
    // BUTTON LOADING STATE
    // -----------------------------------------------------

    function setButtonLoading(button, loading, message = "Processing...") {
        if (!button) return;

        if (loading) {
            if (!button.dataset.originalHtml) {
                button.dataset.originalHtml = button.innerHTML;
            }

            button.disabled = true;
            button.textContent = message;
        } else {
            button.disabled = false;

            if (button.dataset.originalHtml) {
                button.innerHTML = button.dataset.originalHtml;
                delete button.dataset.originalHtml;
            }
        }
    }

    // -----------------------------------------------------
    // WORKFLOW NAVIGATION
    // -----------------------------------------------------

    
    function goToStep(stepNumber) {
        if (stepNumber < 1 || stepNumber > 5) return;

        const panel = $(`[data-panel="${stepNumber}"]`);

        if (!panel) {
            console.error(`Panel ${stepNumber} was not found.`);
            return;
        }

        // Show the requested panel first.
        $$("[data-panel]").forEach((item) => {
            item.hidden = Number(item.dataset.panel) !== stepNumber;
        });

        state.currentStep = stepNumber;

        $$(".steps .step").forEach((button) => {
            const number = Number(button.dataset.step);

            button.classList.toggle("active", number === stepNumber);
            button.classList.toggle("completed", number < stepNumber);

            if (number === stepNumber) {
                button.setAttribute("aria-current", "step");
            } else {
                button.removeAttribute("aria-current");
            }

            button.disabled = number > getMaximumStep();
        });

            hideNotice();

            window.scrollTo({
                top: 0,
                behavior: "smooth"
        });
    }


    function getMaximumStep() {
        if (!state.inspectionId) return 1;
        if (!state.uploadedImages.length) return 2;
        if (!state.extractionCompleted) return 3;
        if (!state.verificationCompleted) return 4;

        return 5;
    }

    function enableStep(stepNumber) {
        const button = $(
            `.steps .step[data-step="${stepNumber}"]`
        );

        if (button) {
            button.disabled = false;
        }
    }

    function updateInspectionContext() {
        const number = state.inspectionNumber || "—";
        const product = state.productName || "—";

        if (elements.imageInspectionNumber) {
            elements.imageInspectionNumber.textContent = number;
        }

        if (elements.imageProductName) {
            elements.imageProductName.textContent = product;
        }

        if (elements.extractInspectionNumber) {
            elements.extractInspectionNumber.textContent = number;
        }

        if (elements.verifyInspectionNumber) {
            elements.verifyInspectionNumber.textContent = number;
        }

        if (elements.resultInspectionNumber) {
            elements.resultInspectionNumber.textContent = number;
        }

        if (elements.extractImageCount) {
            elements.extractImageCount.textContent =
                String(state.uploadedImages.length);
        }
    }

    // -----------------------------------------------------
    // STEP 1: CREATE INSPECTION
    //
    // POST /api/inspections/inspections/
    // Body: {"product": 1} or {"product": null}
    // -----------------------------------------------------

    async function createInspection() {
        if (state.busy) return;

        const imageOnly = elements.imageOnly.checked;

        const rawProductId = elements.productId.value.trim();

        let productId = null;

        if (!imageOnly) {
            if (!rawProductId) {
                showError(
                    "Enter an existing Product ID or select image-only inspection."
                );
                elements.productId.focus();
                return;
            }

            productId = Number(rawProductId);

            if (!Number.isSafeInteger(productId) || productId < 1) {
                showError("Enter a valid positive Product ID.");
                return;
            }
        }

        state.busy = true;
        setButtonLoading(
            elements.createInspection,
            true,
            "Creating..."
        );

        try {
            const payload = {
                product: productId
            };

            const result = await apiRequest(API_BASE, {
                method: "POST",
                body: JSON.stringify(payload)
            });

            if (!result.id) {
                throw new Error(
                    "The API did not return an inspection ID."
                );
            }

            state.inspectionId = result.id;
            state.inspectionNumber = result.inspection_number;
            state.inspectionStatus = result.status;
            state.productId = productId;
            state.productName = imageOnly
                ? "Image-only inspection"
                : `Product ID: ${productId}`;

            state.uploadedImages = [];
            state.extractionCompleted = false;
            state.verificationCompleted = false;
            state.aiData = {};
            state.verifiedData = null;

            updateInspectionContext();

            enableStep(2);
            goToStep(2);

            showSuccess(
                `Inspection ${state.inspectionNumber} created successfully.`
            );

        } catch (error) {
            console.error("Create inspection failed:", error);
            showError(error.message);

        } finally {
            state.busy = false;
            setButtonLoading(elements.createInspection, false);
        }
    }

    // -----------------------------------------------------
    // STEP 2: SELECT IMAGES + PREVIEW
    // -----------------------------------------------------

    function validateImageFiles(files) {
        if (!files.length) {
            return "Select at least one image.";
        }

        for (const file of files) {
            if (!file.type.startsWith("image/")) {
                return `${file.name} is not an image file.`;
            }

            if (
                ALLOWED_IMAGE_TYPES.length &&
                !ALLOWED_IMAGE_TYPES.includes(file.type)
            ) {
                return `${file.name} uses an unsupported image format.`;
            }

            if (file.size > MAX_IMAGE_SIZE) {
                return `${file.name} exceeds the 10 MB file-size limit.`;
            }

            if (file.size === 0) {
                return `${file.name} is empty.`;
            }
        }

        return null;
    }

    function renderImagePreviews() {
        const files = [...elements.images.files];

        elements.imagePreview.replaceChildren();

        if (!files.length) {
            elements.imageSelectionInfo.textContent =
                "No images selected.";
            return;
        }

        const validationError = validateImageFiles(files);

        if (validationError) {
            elements.imageSelectionInfo.textContent = validationError;
            showError(validationError);
            return;
        }

        files.forEach((file, index) => {
            const card = document.createElement("div");
            card.className = "image-preview-card";

            const image = document.createElement("img");
            image.src = URL.createObjectURL(file);
            image.alt = `Selected label image ${index + 1}`;

            image.addEventListener("load", () => {
                URL.revokeObjectURL(image.src);
            }, { once: true });

            const name = document.createElement("p");
            name.textContent = file.name;

            const size = document.createElement("small");
            size.textContent =
                `${(file.size / (1024 * 1024)).toFixed(2)} MB`;

            card.append(image, name, size);
            elements.imagePreview.appendChild(card);
        });

        const totalSize = files.reduce(
            (sum, file) => sum + file.size,
            0
        );

        elements.imageSelectionInfo.textContent =
            `${files.length} image(s) selected · ` +
            `${(totalSize / (1024 * 1024)).toFixed(2)} MB total.`;

        hideNotice();
    }

    // -----------------------------------------------------
    // UPLOAD IMAGES
    //
    // POST /api/inspections/inspections/{id}/images/
    // Each request contains:
    // image: file
    // image_type: FRONT, BACK, SIDE, INGREDIENTS,
    //             NUTRITION or OTHER
    // -----------------------------------------------------

    async function uploadImages() {
        if (state.busy) return;

        if (!state.inspectionId) {
            showError("Create an inspection before uploading images.");
            return;
        }

        const files = [...elements.images.files];

        const validationError = validateImageFiles(files);

        if (validationError) {
            showError(validationError);
            return;
        }

        state.busy = true;

        setButtonLoading(
            elements.uploadImages,
            true,
            "Uploading..."
        );

        const uploaded = [];

        try {
            for (let index = 0; index < files.length; index++) {
                const file = files[index];

                const formData = new FormData();
                formData.append("image", file);

                // The first selected image is the front label.
                // Additional images are recorded as OTHER unless
                // a future UI allows choosing individual image types.
                formData.append(
                    "image_type",
                    index === 0 ? "FRONT" : "OTHER"
                );

                const result = await apiRequest(
                    `${API_BASE}${state.inspectionId}/images/`,
                    {
                        method: "POST",
                        body: formData
                    }
                );

                uploaded.push(result);
            }

            state.uploadedImages = uploaded;

            updateInspectionContext();

            elements.extractImageCount.textContent =
                String(uploaded.length);

            enableStep(3);
            goToStep(3);

            showSuccess(
                `${uploaded.length} image(s) uploaded successfully.`
            );

        } catch (error) {
            console.error("Image upload failed:", error);

            // Preserve successfully uploaded images if a later upload
            // fails, so they are not forgotten by the UI.
            state.uploadedImages = uploaded;
            updateInspectionContext();

            if (uploaded.length) {
                showError(
                    `${uploaded.length} image(s) uploaded successfully, ` +
                    `but another upload failed: ${error.message}. ` +
                    "Select only the remaining images and upload again."
                );
            } else {
                showError(error.message);
            }

        } finally {
            state.busy = false;
            setButtonLoading(elements.uploadImages, false);
        }
    }

    // -----------------------------------------------------
    // STEP 3: OCR + AI EXTRACTION
    //
    // OCR:
    // POST /api/inspections/inspections/{id}/ocr/
    //
    // AI:
    // POST /api/inspections/inspections/{id}/ai_analysis/
    // -----------------------------------------------------

    function setProcessingStatus(element, message) {
        if (element) {
            element.textContent = message;
        }
    }

    function renderExtractionOutput(data) {
        if (elements.extractionOutput) {
            elements.extractionOutput.textContent =
                JSON.stringify(data, null, 2);
        }
    }

    async function runExtraction() {
        if (state.busy) return;

        if (!state.inspectionId) {
            showError("Create an inspection first.");
            return;
        }

        if (!state.uploadedImages.length) {
            showError("Upload at least one image before extraction.");
            return;
        }

        state.busy = true;
        state.extractionCompleted = false;

        elements.openVerification.disabled = true;

        setButtonLoading(
            elements.runExtraction,
            true,
            "Processing OCR..."
        );

        setProcessingStatus(elements.ocrStatus, "Processing...");
        setProcessingStatus(elements.aiStatus, "Waiting for OCR");

        try {
            // FIRST: OCR
            const ocrResult = await apiRequest(
                `${API_BASE}${state.inspectionId}/ocr/`,
                {
                    method: "POST"
                }
            );

            state.inspectionStatus =
                ocrResult.inspection_status || state.inspectionStatus;

            setProcessingStatus(
                elements.ocrStatus,
                `${ocrResult.succeeded ?? 0} succeeded, ` +
                `${ocrResult.failed ?? 0} failed`
            );

            renderExtractionOutput({
                stage: "OCR",
                ...ocrResult
            });

            const successfulOCR = Number(ocrResult.succeeded || 0);

            if (!successfulOCR) {
                throw new Error(
                    "OCR did not succeed for any image. Check the uploaded images before retrying."
                );
            }

            // SECOND: AI extraction
            setProcessingStatus(
                elements.aiStatus,
                "AI extraction in progress..."
            );

            setButtonLoading(
                elements.runExtraction,
                true,
                "Running AI extraction..."
            );

            const aiResult = await apiRequest(
                `${API_BASE}${state.inspectionId}/ai_analysis/`,
                {
                    method: "POST"
                }
            );

            if (
                !aiResult.structured_data ||
                typeof aiResult.structured_data !== "object"
            ) {
                throw new Error(
                    "AI extraction returned no structured label data."
                );
            }

            state.aiData = aiResult.structured_data;
            state.inspectionStatus =
                state.inspectionStatus === "FAILED"
                    ? state.inspectionStatus
                    : "VERIFICATION_PENDING";

            state.extractionCompleted = true;

            renderExtractionOutput({
                ocr: {
                    succeeded: ocrResult.succeeded,
                    failed: ocrResult.failed,
                    total_images: ocrResult.total_images
                },
                ai_analysis: aiResult
            });

            setProcessingStatus(
                elements.aiStatus,
                `Completed · Confidence: ${
                    aiResult.confidence ?? "Not provided"
                }`
            );

            elements.openVerification.disabled = false;

            enableStep(4);

            showSuccess(
                "OCR and AI extraction completed. Review the extracted fields before verification."
            );

        } catch (error) {
            console.error("Extraction failed:", error);

            setProcessingStatus(
                elements.aiStatus,
                "Failed: " + error.message
            );

            showError(error.message);

        } finally {
            state.busy = false;
            setButtonLoading(elements.runExtraction, false);
        }
    }

    // -----------------------------------------------------
    // STEP 4: BUILD EDITABLE VERIFICATION FIELDS
    // -----------------------------------------------------

    function findAIValue(fieldName, data) {
        if (!data || typeof data !== "object") {
            return "";
        }

        const aliases = {
            product_name: ["product_name", "productName", "name"],
            brand: ["brand", "brand_name", "brandName"],
            mrp: ["mrp", "maximum_retail_price", "max_retail_price"],
            net_quantity: [
                "net_quantity",
                "net_weight",
                "net_content",
                "quantity"
            ],
            manufacturing_date: [
                "manufacturing_date",
                "mfg_date",
                "manufacture_date"
            ],
            best_before: ["best_before", "best_before_period"],
            expiry_date: ["expiry_date", "expiration_date", "use_by"],
            ingredients: ["ingredients", "ingredient_list"],
            fssai_license: [
                "fssai_license",
                "fssai_license_number",
                "license_number"
            ],
            manufacturer: ["manufacturer", "manufactured_by"],
            packer: ["packer", "packed_by"],
            importer: ["importer", "imported_by"],
            other_declarations: [
                "other_declarations",
                "declarations",
                "other_information"
            ]
        };

        const possibleKeys = aliases[fieldName] || [fieldName];

        // Prefer exact keys, then known aliases.
        for (const key of possibleKeys) {
            if (
                Object.prototype.hasOwnProperty.call(data, key) &&
                data[key] !== null &&
                data[key] !== undefined
            ) {
                return normalizeFieldValue(data[key], fieldName);
            }
        }

        return "";
    }

    function normalizeFieldValue(value, fieldName) {
        if (value === null || value === undefined) {
            return "";
        }

        if (typeof value === "object") {
            if (Array.isArray(value)) {
                return value.map((item) =>
                    typeof item === "object"
                        ? JSON.stringify(item)
                        : String(item)
                ).join(", ");
            }

            // Handle common AI output structures such as
            // {"value": "..."} without discarding the original data.
            if (
                Object.keys(value).length === 1 &&
                Object.prototype.hasOwnProperty.call(value, "value")
            ) {
                return normalizeFieldValue(value.value, fieldName);
            }

            return JSON.stringify(value);
        }

        let result = String(value);

        if (
            ["manufacturing_date", "expiry_date"].includes(fieldName) &&
            result
        ) {
            // Native date inputs require YYYY-MM-DD.
            const match = result.match(/^(\d{4})-(\d{2})-(\d{2})/);

            if (match) {
                return `${match[1]}-${match[2]}-${match[3]}`;
            }
        }

        return result;
    }

    function createVerificationField(definition, value) {
        const wrapper = document.createElement("div");
        wrapper.className = "form-group verification-field";

        const label = document.createElement("label");
        label.htmlFor = `verify-${definition.name}`;
        label.textContent = definition.label;

        let input;

        if (definition.type === "textarea") {
            input = document.createElement("textarea");
            input.rows = 3;
        } else {
            input = document.createElement("input");
            input.type = definition.type;

            if (definition.type === "number") {
                input.step = "0.01";
                input.min = "0";
            }
        }

        input.id = `verify-${definition.name}`;
        input.name = definition.name;
        input.dataset.verificationField = definition.name;
        input.value = value;

        input.autocomplete = "off";

        wrapper.append(label, input);

        return wrapper;
    }

    function renderVerificationFields(aiData, savedData = null) {
        elements.verificationFields.replaceChildren();

        FIELD_DEFINITIONS.forEach((definition) => {
            const savedValue = savedData
                ? savedData[definition.name]
                : undefined;

            const value =
                savedValue !== undefined && savedValue !== null
                    ? normalizeFieldValue(savedValue, definition.name)
                    : findAIValue(definition.name, aiData);

            elements.verificationFields.appendChild(
                createVerificationField(definition, value)
            );
        });
    }

    // -----------------------------------------------------
    // GET VERIFICATION DATA
    //
    // GET /api/inspections/inspections/{id}/verify/
    // -----------------------------------------------------

    async function openVerification() {
        if (state.busy) return;

        if (!state.extractionCompleted) {
            showError("Complete AI extraction before verification.");
            return;
        }

        state.busy = true;

        setButtonLoading(
            elements.openVerification,
            true,
            "Loading fields..."
        );

        try {
            const result = await apiRequest(
                `${API_BASE}${state.inspectionId}/verify/`
            );

            const analysis = result.ai_analysis;

            if (!analysis || !analysis.structured_data) {
                throw new Error(
                    "No completed AI analysis is available for verification."
                );
            }

            state.aiData = analysis.structured_data;
            state.verifiedData = result.verified_data || null;

            renderVerificationFields(
                state.aiData,
                state.verifiedData
            );

            elements.verificationStatus.textContent =
                state.verifiedData?.is_verified
                    ? "Verified"
                    : "Pending";

            updateInspectionContext();

            goToStep(4);

        } catch (error) {
            console.error("Loading verification data failed:", error);
            showError(error.message);

        } finally {
            state.busy = false;
            setButtonLoading(elements.openVerification, false);
        }
    }

    // -----------------------------------------------------
    // SUBMIT INSPECTOR VERIFICATION
    //
    // POST /api/inspections/inspections/{id}/verify/
    //
    // Only model fields are sent. inspector_remarks is not
    // part of VerifiedDataSerializer, so it is not submitted.
    // -----------------------------------------------------

    async function submitVerification(event) {
        event.preventDefault();

        if (state.busy) return;

        if (!state.inspectionId || !state.extractionCompleted) {
            showError("Complete AI extraction before verification.");
            return;
        }

        if (!elements.confirmVerification.checked) {
            showError(
                "Confirm that you reviewed the label against the images."
            );
            elements.confirmVerification.focus();
            return;
        }

        const payload = {};

        const inputs = $$("[data-verification-field]");

        for (const input of inputs) {
            const fieldName = input.dataset.verificationField;
            const value = input.value.trim();

            if (fieldName === "mrp" && value !== "") {
                const amount = Number(value);

                if (!Number.isFinite(amount) || amount < 0) {
                    showError("Enter a valid non-negative MRP.");
                    input.focus();
                    return;
                }

                payload[fieldName] = amount;
                continue;
            }

            // Empty date/decimal fields are omitted to avoid
            // sending invalid empty strings to Django.
            if (value !== "") {
                payload[fieldName] = value;
            }
        }

        if (Object.keys(payload).length === 0) {
            showError(
                "Enter or confirm at least one label field before submitting verification."
            );
            return;
        }

        state.busy = true;

        setButtonLoading(
            elements.submitVerification,
            true,
            "Saving verification..."
        );

        try {
            const result = await apiRequest(
                `${API_BASE}${state.inspectionId}/verify/`,
                {
                    method: "POST",
                    body: JSON.stringify(payload)
                }
            );

            state.verifiedData = result.verified_data || null;
            state.verificationCompleted = true;
            state.inspectionStatus =
                result.inspection_status || "VERIFIED";

            updateInspectionContext();

            if (elements.verificationStatus) {
                elements.verificationStatus.textContent = "Verified";
            }

            if (elements.resultHeading) {
                elements.resultHeading.textContent =
                    "Verification Submitted";
            }

            if (elements.resultDescription) {
                elements.resultDescription.textContent =
                    result.detail ||
                    "Inspector verification completed successfully.";
            }

            if (elements.resultInspectionStatus) {
                elements.resultInspectionStatus.textContent =
                    state.inspectionStatus;
            }

            if (elements.resultImageCount) {
                elements.resultImageCount.textContent =
                    String(state.uploadedImages.length);
            }

            if (elements.resultOutput) {
                elements.resultOutput.replaceChildren();

                const heading = document.createElement("h3");
                heading.textContent = "Next Step";

                const paragraph = document.createElement("p");
                paragraph.textContent =
                    "Inspector verification is saved. Compliance evaluation has not been performed by this workflow.";

                elements.resultOutput.append(heading, paragraph);
            }

            enableStep(5);
            goToStep(5);

            showSuccess(
                "Inspector verification saved successfully."
            );

        } catch (error) {
            console.error("Verification submission failed:", error);
            showError(error.message);

        } finally {
            state.busy = false;
            setButtonLoading(elements.submitVerification, false);
        }
    }

    // -----------------------------------------------------
    // STEP 5: FINISH
    // No completion/evaluation API is currently implemented
    // in the provided views.py.
    // -----------------------------------------------------

    function finishInspection() {
        if (!state.verificationCompleted) {
            showError(
                "Complete inspector verification before finishing."
            );
            return;
        }

        showSuccess(
            `Inspection ${state.inspectionNumber} is verified. ` +
            "Compliance evaluation is a separate workflow."
        );

        // Do not mark the database record COMPLETED here.
        // The supplied backend only sets its status to VERIFIED.
    }

    // -----------------------------------------------------
    // CANCEL
    // -----------------------------------------------------

    function cancelInspection() {
        if (state.inspectionId && !state.verificationCompleted) {
            const confirmed = window.confirm(
                "Leave this inspection? Any saved inspection or uploaded images will remain in the database."
            );

            if (!confirmed) return;
        }

        // Return to the previous browser page if one exists.
        if (window.history.length > 1) {
            window.history.back();
        } else {
            showNotice(
                "You can leave this page using your application's navigation.",
                "info"
            );
        }
    }

    // -----------------------------------------------------
    // EVENT LISTENERS
    // -----------------------------------------------------

    function initialize() {
        // Product selection
        elements.imageOnly.addEventListener("change", () => {
            elements.productId.disabled =
                elements.imageOnly.checked;

            if (elements.imageOnly.checked) {
                elements.productId.value = "";
            }

            hideNotice();
        });

        // Create inspection
        elements.createInspection.addEventListener(
            "click",
            createInspection
        );

        // Image selection and preview
        elements.images.addEventListener(
            "change",
            renderImagePreviews
        );

        // Drag and drop image upload
        elements.uploadArea.addEventListener("dragover", (event) => {
            event.preventDefault();
            elements.uploadArea.classList.add("drag-over");
        });

        elements.uploadArea.addEventListener("dragleave", () => {
            elements.uploadArea.classList.remove("drag-over");
        });

        elements.uploadArea.addEventListener("drop", (event) => {
            event.preventDefault();
            elements.uploadArea.classList.remove("drag-over");

            const droppedFiles = [...event.dataTransfer.files];

            if (!droppedFiles.length) return;

            const transfer = new DataTransfer();

            droppedFiles.forEach((file) => {
                transfer.items.add(file);
            });

            elements.images.files = transfer.files;

            renderImagePreviews();
        });

        // Upload images
        elements.uploadImages.addEventListener(
            "click",
            uploadImages
        );

        // OCR and AI
        elements.runExtraction.addEventListener(
            "click",
            runExtraction
        );

        // Verification
        elements.openVerification.addEventListener(
            "click",
            openVerification
        );

        elements.verificationForm.addEventListener(
            "submit",
            submitVerification
        );

        // Back buttons
        $$("[data-previous]").forEach((button) => {
            button.addEventListener("click", () => {
                const previousStep = Number(
                    button.dataset.previous
                );

                goToStep(previousStep);
            });
        });

        // Workflow step navigation
        $$(".steps .step").forEach((button) => {
            button.addEventListener("click", () => {
                if (!button.disabled) {
                    goToStep(Number(button.dataset.step));
                }
            });
        });

        // Cancel
        $(".btn-cancel")?.addEventListener("click", (event) => {
            event.preventDefault();
            cancelInspection();
        });

        // Finish
        elements.finishInspection.addEventListener(
            "click",
            finishInspection
        );

        // Initial page state
        elements.productId.disabled = elements.imageOnly.checked;

        goToStep(1);

        console.info("Label Inspection JavaScript initialized.");
    }

    // -----------------------------------------------------
    // START APPLICATION
    // -----------------------------------------------------

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initialize,
            { once: true }
        );
    } else {
        initialize();
    }
})();

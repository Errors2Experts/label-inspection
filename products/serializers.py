from rest_framework import serializers

from .gtin import to_gtin14, validate_gtin
from .models import Product

IMAGE_FIELDS = ['front_image', 'back_image', 'left_image', 'right_image']
MAX_IMAGE_MB = 5


class ProductSerializer(serializers.ModelSerializer):
    # Declared explicitly: people type barcodes with spaces/dashes, so allow extra length here and let
    # `validate_gtin` enforce the real 8/12/13/14-digit rule after cleaning.
    gtin = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=40)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='')

    class Meta:
        model = Product
        fields = [
            'id', 'gtin', 'name', 'brand', 'category', 'net_quantity', 'mrp', 'ingredients', 'allergens',
            'manufacturer', 'fssai_license', 'country_of_origin', 'image_url',
            'front_image', 'back_image', 'left_image', 'right_image',
            'source', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'source', 'created_by_name', 'created_at', 'updated_at']

    def validate_gtin(self, value):
        if not value or not value.strip():
            return ''
        if self.instance is not None and value.strip() == self.instance.gtin:
            return value.strip()  # unchanged barcode (e.g. demo data): editing other fields must still work
        try:
            return validate_gtin(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Product name is required.')
        return value

    def validate(self, attrs):
        gtin = attrs.get('gtin')
        if gtin:
            clash = Product.objects.filter(gtin14=to_gtin14(gtin))
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError({'gtin': 'A product with this barcode already exists.'})

        errors = {}
        for field in IMAGE_FIELDS:
            f = attrs.get(field)
            if f and f.size > MAX_IMAGE_MB * 1024 * 1024:
                errors[field] = f'Image must be {MAX_IMAGE_MB} MB or smaller.'
        # The back of the pack carries the barcode, so it is required when a product is added.
        if self.instance is None and not attrs.get('back_image'):
            errors['back_image'] = 'The back image (showing the barcode) is required.'
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
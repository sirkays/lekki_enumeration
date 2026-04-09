from rest_framework import serializers
from .models import LekkiEnumeration, BillDistribution


class LekkiEnumerationSerializer(serializers.ModelSerializer):
    full_address = serializers.SerializerMethodField()

    class Meta:
        model = LekkiEnumeration
        fields = '__all__'

    def get_full_address(self, obj):
        parts = [
            obj.house_number or '',
            obj.street_name or '',
        ]
        return " ".join([p for p in parts if p]).strip()


class BillDistributionSerializer(serializers.ModelSerializer):
    captured_by = serializers.StringRelatedField()
    street_name = serializers.CharField(source='lekki_enum.street_name', read_only=True)
    house_number = serializers.CharField(source='lekki_enum.house_number', read_only=True)
    owner_name = serializers.CharField(source='lekki_enum.owner_name', read_only=True)
    full_address = serializers.SerializerMethodField()

    class Meta:
        model = BillDistribution
        fields = [
            'id',
            'property_id',
            'year',
            'bill_image',
            'date_captured',
            'captured_by',
            'latitude',
            'longitude',
            'street_name',
            'house_number',
            'owner_name',
            'full_address',
        ]

    def get_full_address(self, obj):
        parts = [
            obj.lekki_enum.house_number or '',
            obj.lekki_enum.street_name or '',
        ]
        return " ".join([p for p in parts if p]).strip()
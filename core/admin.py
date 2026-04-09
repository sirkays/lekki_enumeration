from django.contrib import admin
from .models import LekkiEnumeration, BillDistribution


@admin.register(LekkiEnumeration)
class LekkiEnumerationAdmin(admin.ModelAdmin):
    list_display = (
        "property_id",
        "street_name",
        "house_number",
        "property_type",
        "owner_name",
        "owner_phone",
        "business_type",
        "revenue_category",
        "completeness_status",
        "latitude",
        "longitude",
    )
    search_fields = (
        "property_id",
        "street_name",
        "house_number",
        "owner_name",
        "owner_phone",
        "business_type",
        "business_name_1",
        "business_name_2",
        "business_name_3",
        "business_name_4",
        "owner_email",
        "contact_email",
        "email",
        "confirmed_house_number",
        "assigned_house_number",
    )
    list_filter = (
        "property_type",
        "revenue_category",
        "completeness_status",
        "no_of_floors",
        "no_of_units",
    )
    readonly_fields = (
        "property_id",
        "created_at",
        "enumeration_date",
        "latitude",
        "longitude",
        "geom",
    )
    ordering = ("property_id",)
    list_per_page = 50

    fieldsets = (
        ("Property Information", {
            "fields": (
                "property_id",
                "street_name",
                "house_number",
                "confirmed_house_number",
                "assigned_house_number",
                "property_type",
                "business_type",
                "revenue_category",
                "no_of_floors",
                "no_of_units",
                "completeness_status",
            )
        }),
        ("Owner Details", {
            "fields": (
                "owner_name",
                "owner_phone",
                "owner_email",
                "owner_address",
            )
        }),
        ("Contact Details", {
            "fields": (
                "contact_name",
                "contact_phone",
                "contact_email",
                "contact_address",
                "email",
            )
        }),
        ("Business Names", {
            "fields": (
                "business_name_1",
                "business_name_2",
                "business_name_3",
                "business_name_4",
            )
        }),
        ("Location / GIS", {
            "fields": (
                "latitude",
                "longitude",
                "area_in_me",
                "confidence",
                "full_plus_field",
                "geom",
            )
        }),
        ("Photos", {
            "fields": (
                "photo_front",
                "photo_gate",
                "photo_signage",
                "photo_street",
            )
        }),
        ("Audit / Metadata", {
            "fields": (
                "created_at",
                "enumeration_date",
            )
        }),
    )


@admin.register(BillDistribution)
class BillDistributionAdmin(admin.ModelAdmin):
    list_display = (
        "property_id",
        "lekki_enum",
        "year",
        "captured_by",
        "date_captured",
        "latitude",
        "longitude",
    )
    search_fields = (
        "property_id",
        "lekki_enum__property_id",
        "lekki_enum__street_name",
        "lekki_enum__house_number",
        "lekki_enum__owner_name",
        "captured_by__email",
        "captured_by__user_id",
    )
    list_filter = (
        "year",
        "date_captured",
        "captured_by",
    )
    readonly_fields = ("date_captured",)
    autocomplete_fields = ("lekki_enum", "captured_by")
    ordering = ("-date_captured",)
    list_per_page = 50

    fieldsets = (
        ("Distribution Record", {
            "fields": (
                "lekki_enum",
                "property_id",
                "year",
                "bill_image",
            )
        }),
        ("Capture Details", {
            "fields": (
                "captured_by",
                "date_captured",
                "latitude",
                "longitude",
            )
        }),
    )


    
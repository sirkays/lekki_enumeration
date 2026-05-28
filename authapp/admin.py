from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, SessionToken,UserProfile,RoutePayTransaction
from django.utils.html import format_html
import json

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display = (
        "email",
        "user_id",
        "is_staff",
        "is_active",
        "is_superuser",
        "date_joined",
    )
    search_fields = ("email", "user_id")
    list_filter = ("is_staff", "is_active", "is_superuser", "groups")
    ordering = ("-date_joined",)
    list_per_page = 50

    fieldsets = (
        (None, {"fields": ("email", "user_id", "password")}),
        ("Permissions", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "user_id",
                "password1",
                "password2",
                "is_staff",
                "is_active",
                "is_superuser",
            ),
        }),
    )

    readonly_fields = ("date_joined", "last_login")


@admin.register(SessionToken)
class SessionTokenAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "short_key",
        "created_at",
        "expires_at",
        "is_active",
    )
    search_fields = (
        "user__email",
        "user__user_id",
        "key",
    )
    list_filter = (
        "is_active",
        "created_at",
        "expires_at",
    )
    readonly_fields = ("created_at", "short_key")
    autocomplete_fields = ("user",)
    ordering = ("-created_at",)
    list_per_page = 50

    fieldsets = (
        ("Token Details", {
            "fields": (
                "user",
                "key",
                "short_key",
                "is_active",
                "meta",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "expires_at",
            )
        }),
    )

    @admin.display(description="Token")
    def short_key(self, obj):
        return f"{obj.key[:10]}..." if obj.key else "-"






# -------------------------------------------------------------------
# Inline Profile (shown inside User)
# -------------------------------------------------------------------

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    readonly_fields = ('profile_image_preview',)

    def profile_image_preview(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" width="100" height="100" style="border-radius:8px;" />',
                obj.profile_image.url
            )
        return "No Image"

    profile_image_preview.short_description = "Profile Image Preview"


# -------------------------------------------------------------------
# User Profile Admin
# -------------------------------------------------------------------

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user_id_display',
        'full_name',
        'phone',
        'role',
        'is_visualizer_display',
        'profile_image_preview',
    )

    list_filter = ('role',)
    search_fields = (
        'user__user_id',
        'user__email',
        'full_name',
        'phone',
    )

    readonly_fields = ('profile_image_preview',)

    fieldsets = (
        ("User Info", {
            'fields': ('user',)
        }),
        ("Profile Details", {
            'fields': ('full_name', 'phone', 'role')
        }),
        ("Profile Image", {
            'fields': ('profile_image', 'profile_image_preview')
        }),
    )

    def user_id_display(self, obj):
        return obj.user.user_id
    user_id_display.short_description = "User ID"

    def is_visualizer_display(self, obj):
        return obj.is_visualizer
    is_visualizer_display.boolean = True
    is_visualizer_display.short_description = "Visualizer Access"

    def profile_image_preview(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" width="60" height="60" style="border-radius:6px;" />',
                obj.profile_image.url
            )
        return "No Image"

    profile_image_preview.short_description = "Image"



@admin.register(RoutePayTransaction)
class RoutePayTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "merchant_reference",
        "transaction_reference",
        "payee_id",
        "customer_name",
        "formatted_amount",
        "status_badge",
        "is_successful",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "is_successful",
        "payment_status",
        "currency",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "payee_id",
        "merchant_reference",
        "transaction_reference",
        "customer_name",
        "customer_email",
        "customer_phone",
        "payment_description",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "formatted_amount",
        "status_badge",
        "pretty_metadata",
        "pretty_raw_init_response",
        "pretty_raw_status_response",
    )

    date_hierarchy = "created_at"

    ordering = ("-created_at",)

    list_per_page = 25

    actions = (
        "mark_as_successful",
        "mark_as_pending",
        "mark_as_failed",
    )

    fieldsets = (
        (
            "Transaction References",
            {
                "fields": (
                    "payee_id",
                    "merchant_reference",
                    "transaction_reference",
                )
            },
        ),
        (
            "Customer Information",
            {
                "fields": (
                    "customer_name",
                    "customer_email",
                    "customer_phone",
                )
            },
        ),
        (
            "Payment Details",
            {
                "fields": (
                    "amount",
                    "formatted_amount",
                    "currency",
                    "payment_status",
                    "payment_description",
                    "is_successful",
                    "status_badge",
                )
            },
        ),
        (
            "RoutePay / Metadata",
            {
                "classes": ("collapse",),
                "fields": (
                    "pretty_metadata",
                    "pretty_raw_init_response",
                    "pretty_raw_status_response",
                ),
            },
        ),
        (
            "System Dates",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def formatted_amount(self, obj):
        if obj.amount is None:
            return "-"

        return f"{obj.currency or 'NGN'} {obj.amount:,.2f}"

    formatted_amount.short_description = "Amount"

    def status_badge(self, obj):
        status = obj.payment_status
        description = obj.payment_description or ""

        if obj.is_successful or status == 0:
            color = "#16a34a"
            background = "#dcfce7"
            label = "Successful"
        elif status in [250, 260]:
            color = "#d97706"
            background = "#fef3c7"
            label = description or "Pending / Processing"
        elif status in [550, 220]:
            color = "#dc2626"
            background = "#fee2e2"
            label = description or "Failed / Cancelled"
        elif status == 210:
            color = "#2563eb"
            background = "#dbeafe"
            label = description or "Already Processed"
        else:
            color = "#4b5563"
            background = "#f3f4f6"
            label = description or "Unknown"

        return format_html(
            '<span style="'
            'display:inline-block;'
            'padding:4px 10px;'
            'border-radius:999px;'
            'font-size:12px;'
            'font-weight:700;'
            'color:{};'
            'background:{};'
            '">{}</span>',
            color,
            background,
            label,
        )

    status_badge.short_description = "Payment Status"

    def pretty_metadata(self, obj):
        return self._pretty_json(obj.metadata)

    pretty_metadata.short_description = "Metadata"

    def pretty_raw_init_response(self, obj):
        return self._pretty_json(obj.raw_init_response)

    pretty_raw_init_response.short_description = "RoutePay Init Response"

    def pretty_raw_status_response(self, obj):
        return self._pretty_json(obj.raw_status_response)

    pretty_raw_status_response.short_description = "RoutePay Status Response"

    def _pretty_json(self, value):
        if not value:
            return "-"

        try:
            pretty = json.dumps(value, indent=2, ensure_ascii=False)
        except TypeError:
            pretty = str(value)

        return format_html(
            '<pre style="'
            'white-space:pre-wrap;'
            'word-break:break-word;'
            'background:#f8fafc;'
            'border:1px solid #e5e7eb;'
            'border-radius:8px;'
            'padding:12px;'
            'max-height:420px;'
            'overflow:auto;'
            'font-size:12px;'
            'line-height:1.5;'
            '">{}</pre>',
            pretty,
        )

    @admin.action(description="Mark selected transactions as successful")
    def mark_as_successful(self, request, queryset):
        updated = queryset.update(
            is_successful=True,
            payment_status=0,
            payment_description="Successful",
        )

        self.message_user(
            request,
            f"{updated} transaction(s) marked as successful.",
        )

    @admin.action(description="Mark selected transactions as pending")
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(
            is_successful=False,
            payment_status=250,
            payment_description="Pending",
        )

        self.message_user(
            request,
            f"{updated} transaction(s) marked as pending.",
        )

    @admin.action(description="Mark selected transactions as failed")
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(
            is_successful=False,
            payment_status=550,
            payment_description="Failed",
        )

        self.message_user(
            request,
            f"{updated} transaction(s) marked as failed.",
        )
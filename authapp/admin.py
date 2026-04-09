from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, SessionToken,UserProfile
from django.utils.html import format_html

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



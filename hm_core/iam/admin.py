# backend/hm_core/iam/admin.py
from __future__ import annotations

from django.contrib import admin

from hm_core.iam.models import FacilityMembership, Permission, Role, RolePermission, UserProfile


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "description")
    search_fields = ("code", "description")
    ordering = ("code",)


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0
    autocomplete_fields = ("permission",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tenant", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = ("tenant",)
    inlines = [RolePermissionInline]
    ordering = ("tenant", "code")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "tenant", "is_active", "created_at", "updated_at")
    list_filter = ("tenant", "is_active")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user", "tenant")
    ordering = ("-created_at",)


@admin.register(FacilityMembership)
class FacilityMembershipAdmin(admin.ModelAdmin):
    list_display = ("tenant", "facility", "user_profile", "role", "is_active")
    list_filter = ("tenant", "facility", "role", "is_active")
    search_fields = ("facility__name", "facility__code", "user_profile__user__username", "user_profile__user__email")
    autocomplete_fields = ("tenant", "facility", "user_profile", "role")

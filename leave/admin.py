from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Staff, Leave, LeaveType, Threshold


@admin.register(Staff)
class StaffAdmin(UserAdmin):
    list_display = ["username", "name", "role", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff"]
    fieldsets = UserAdmin.fieldsets + (("職員情報", {"fields": ("name", "role")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("職員情報", {"fields": ("name", "role", "is_active")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser


@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ["date", "staff", "kind", "start", "end"]
    list_filter = ["date", "staff__role", "kind"]

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        from django.db import transaction

        with transaction.atomic():
            staff_id = request.POST.get("staff", "")
            if request.method == "POST" and staff_id.isdecimal():
                Staff.objects.select_for_update().filter(pk=int(staff_id)).first()
            return super().changeform_view(request, object_id, form_url, extra_context)


admin.site.register(LeaveType)
admin.site.register(Threshold)
admin.site.site_header = "休暇予定共有 / 管理"

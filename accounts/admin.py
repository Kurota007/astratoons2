from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile, CosmeticBadge, UserBadge

class UserBadgeInline(admin.TabularInline):
    model = UserBadge
    extra = 1
    autocomplete_fields = ('badge',)
    verbose_name = "Badge no Inventário"
    verbose_name_plural = "Inventário de Badges"

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Perfil'
    fk_name = 'user'

class CustomUserAdmin(BaseUserAdmin):
    inlines = (ProfileInline, UserBadgeInline)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(CosmeticBadge)
class CosmeticBadgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_staff_only', 'is_vip_badge')
    search_fields = ('name',)
    list_filter = ('is_staff_only', 'is_vip_badge')
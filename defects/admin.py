from django.contrib import admin

from .models import DefectComment, DefectReport, DefectStatusHistory, Product, ProductDeveloper


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("product_id", "name", "owner_id")
    search_fields = ("product_id", "owner_id", "name")


@admin.register(ProductDeveloper)
class ProductDeveloperAdmin(admin.ModelAdmin):
    list_display = ("developer_id", "product")
    search_fields = ("developer_id", "product__product_id")
    list_filter = ("product",)


@admin.register(DefectReport)
class DefectReportAdmin(admin.ModelAdmin):
    list_display = ("report_id", "product", "status", "severity", "priority", "assignee_id", "tester_id")
    list_filter = ("status", "severity", "priority", "product")
    search_fields = ("report_id", "title", "product__product_id", "tester_id", "assignee_id")


@admin.register(DefectComment)
class DefectCommentAdmin(admin.ModelAdmin):
    list_display = ("defect", "author_id", "created_at")
    search_fields = ("defect__report_id", "author_id", "text")


@admin.register(DefectStatusHistory)
class DefectStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("defect", "from_status", "to_status", "actor_id", "changed_at")
    list_filter = ("from_status", "to_status")
    search_fields = ("defect__report_id", "actor_id")

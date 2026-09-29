from django.contrib import admin

from payroll.models import EmployeeCompensation, PayrollPolicy, PayrollRun, Payslip


@admin.register(PayrollPolicy)
class PayrollPolicyAdmin(admin.ModelAdmin):
    list_display = ("organization", "currency", "pay_frequency", "annual_leave_days", "sick_leave_days")


@admin.register(EmployeeCompensation)
class EmployeeCompensationAdmin(admin.ModelAdmin):
    list_display = ("employee", "pay_type", "basic_salary", "hire_date")
    search_fields = ("employee__employee_id", "employee__first_name", "employee__last_name")


class PayslipInline(admin.TabularInline):
    model = Payslip
    extra = 0
    readonly_fields = ("employee", "gross_pay", "total_deductions", "net_pay")


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ("organization", "period_start", "period_end", "status")
    list_filter = ("status", "organization")
    inlines = [PayslipInline]

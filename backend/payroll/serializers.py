from decimal import Decimal

from rest_framework import serializers

from payroll.models import EmployeeCompensation, PayrollPolicy, PayrollRun, Payslip


class PayrollPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollPolicy
        fields = [
            "currency",
            "pay_frequency",
            "working_days_per_month",
            "hours_per_day",
            "annual_leave_days",
            "sick_leave_days",
            "other_leave_days",
            "annual_leave_paid",
            "sick_leave_paid",
            "other_leave_paid",
            "unpaid_leave_allowed",
            "leave_year_start_month",
            "carry_forward_annual",
            "carry_forward_max_days",
            "probation_months",
            "probation_blocks_annual",
            "enforce_leave_balance",
            "holiday_paid",
            "weekend_paid",
            "absent_deduct",
            "half_day_pay_factor",
            "late_count_free",
            "late_penalty_mode",
            "late_penalty_amount",
            "early_leave_deduct",
            "early_leave_as_half_day",
            "overtime_paid",
            "overtime_multiplier",
            "overtime_min_minutes",
            "overtime_requires_approval",
            "tax_percent",
            "provident_fund_percent",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_leave_year_start_month(self, value):
        if value < 1 or value > 12:
            raise serializers.ValidationError("Must be 1–12")
        return value

    def validate_half_day_pay_factor(self, value):
        if value < 0 or value > 1:
            raise serializers.ValidationError("Must be between 0 and 1")
        return value


class EmployeeCompensationSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    department = serializers.CharField(source="employee.department_name", read_only=True)
    designation = serializers.CharField(source="employee.designation", read_only=True)
    is_active = serializers.BooleanField(source="employee.is_active", read_only=True)
    gross = serializers.SerializerMethodField()
    salary_set = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeCompensation
        fields = [
            "employee_id",
            "employee_name",
            "department",
            "designation",
            "is_active",
            "pay_type",
            "basic_salary",
            "housing_allowance",
            "transport_allowance",
            "medical_allowance",
            "other_allowance",
            "other_deduction",
            "hire_date",
            "bank_name",
            "account_title",
            "account_number",
            "notes",
            "gross",
            "salary_set",
            "updated_at",
        ]
        read_only_fields = [
            "employee_id",
            "employee_name",
            "department",
            "designation",
            "is_active",
            "gross",
            "salary_set",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.display_name

    def get_gross(self, obj):
        return f"{obj.monthly_gross:.2f}"

    def get_salary_set(self, obj):
        return obj.basic_salary > 0


class PayslipSerializer(serializers.ModelSerializer):
    employee_id = serializers.CharField(source="employee.employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    department = serializers.CharField(source="employee.department_name", read_only=True)
    period_start = serializers.DateField(source="run.period_start", read_only=True)
    period_end = serializers.DateField(source="run.period_end", read_only=True)
    run_status = serializers.CharField(source="run.status", read_only=True)

    class Meta:
        model = Payslip
        fields = [
            "id",
            "employee_id",
            "employee_name",
            "department",
            "period_start",
            "period_end",
            "run_status",
            "pay_type",
            "working_days",
            "present_days",
            "late_days",
            "half_days",
            "absent_days",
            "paid_leave_days",
            "unpaid_leave_days",
            "overtime_minutes",
            "early_leave_days",
            "basic_pay",
            "allowances",
            "overtime_pay",
            "absent_deduction",
            "late_deduction",
            "unpaid_leave_deduction",
            "half_day_deduction",
            "early_leave_deduction",
            "tax",
            "provident_fund",
            "other_deduction",
            "gross_pay",
            "total_deductions",
            "net_pay",
            "breakdown",
        ]

    def get_employee_name(self, obj):
        return obj.employee.display_name


class PayrollRunSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()
    finalized_by_email = serializers.SerializerMethodField()
    payslip_count = serializers.IntegerField(read_only=True)
    totals = serializers.SerializerMethodField()
    payslips = PayslipSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollRun
        fields = [
            "id",
            "period_start",
            "period_end",
            "status",
            "notes",
            "warnings",
            "created_by_email",
            "finalized_by_email",
            "finalized_at",
            "created_at",
            "updated_at",
            "payslip_count",
            "totals",
            "payslips",
        ]
        read_only_fields = fields

    def get_created_by_email(self, obj):
        return obj.created_by.email if obj.created_by_id else None

    def get_finalized_by_email(self, obj):
        return obj.finalized_by.email if obj.finalized_by_id else None

    def get_totals(self, obj):
        slips = list(obj.payslips.all())
        zero = Decimal("0.00")
        return {
            "gross": str(sum((s.gross_pay for s in slips), zero)),
            "deductions": str(sum((s.total_deductions for s in slips), zero)),
            "net": str(sum((s.net_pay for s in slips), zero)),
        }


class PayrollRunListSerializer(PayrollRunSerializer):
    class Meta(PayrollRunSerializer.Meta):
        fields = [f for f in PayrollRunSerializer.Meta.fields if f != "payslips"]


class GeneratePayrollSerializer(serializers.Serializer):
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    def validate(self, attrs):
        if attrs["period_end"] < attrs["period_start"]:
            raise serializers.ValidationError("period_end must be on or after period_start")
        return attrs

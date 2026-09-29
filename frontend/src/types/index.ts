export interface FaceEnrollment {
  id: number
  is_enrolled: boolean
  is_trained: boolean
  total_images: number
  model_version: string
  dataset_folder: string
  profile_image: string | null
  created_at: string
  updated_at: string
}

export interface Shift {
  id: number
  name: string
  kind?: 'fixed' | 'flexible' | 'night' | 'split'
  branch?: number | null
  branch_name?: string | null
  start_time: string
  late_after: string
  end_time: string
  required_hours?: string | number | null
  break_start?: string | null
  break_end?: string | null
  second_start?: string | null
  second_end?: string | null
  grace_minutes?: number
  early_leave_grace_minutes?: number
  overtime_grace_minutes?: number
  is_default: boolean
  is_active: boolean
  employee_count?: number
  created_at?: string
  updated_at?: string
}

export interface ShiftAssignment {
  id: number
  shift: number
  shift_name: string
  start_date: string
  end_date: string | null
  weekdays: number[]
  created_at?: string
  updated_at?: string
}

export interface Branch {
  id: number
  name: string
  code: string
  address: string
  latitude: string | number | null
  longitude: string | number | null
  geofence_radius_m: number | null
  timezone: string
  weekend_days: number[]
  manager: number | null
  manager_email: string | null
  is_default: boolean
  is_active: boolean
  employee_count?: number
  created_at?: string
  updated_at?: string
}

export interface Department {
  id: number
  name: string
  branch?: number | null
  branch_name?: string | null
  is_active: boolean
  sort_order: number
  employee_count?: number
  created_at?: string
  updated_at?: string
}

export type EmploymentType = 'full_time' | 'part_time' | 'contract' | 'intern' | 'temporary' | 'remote'
export type Gender = 'male' | 'female' | 'other' | ''

export interface EmployeeDocument {
  id: number
  title: string
  category: 'contract' | 'id' | 'certificate' | 'other'
  file?: string
  file_url: string
  uploaded_at: string
}

export interface Employee {
  id: number
  employee_id: string
  first_name: string
  last_name: string
  email: string
  phone: string
  national_id?: string
  date_of_birth?: string | null
  gender?: Gender
  address?: string
  guardian_name?: string
  guardian_phone?: string
  guardian_email?: string
  branch?: number | null
  branch_name?: string
  department: number | null
  department_name: string
  designation: string
  employment_type?: EmploymentType
  joining_date?: string | null
  manager?: number | null
  manager_name?: string
  shift: number | null
  shift_detail: Pick<Shift, 'id' | 'name' | 'start_time' | 'late_after' | 'end_time' | 'is_default' | 'is_active'> | null
  is_active: boolean
  has_portal_login?: boolean
  face_enrollment: FaceEnrollment | null
  document_count?: number
  created_at: string
  updated_at: string
}

export interface EmployeeFormData {
  employee_id: string
  first_name: string
  last_name: string
  email: string
  phone: string
  national_id?: string
  date_of_birth?: string
  gender?: Gender
  address?: string
  guardian_name?: string
  guardian_phone?: string
  guardian_email?: string
  branch: number | null
  department: number | null
  designation: string
  employment_type?: EmploymentType
  joining_date?: string
  manager?: number | null
  shift: number | null
  is_active: boolean
}

export interface AttendanceRecord {
  id: number
  employee_id: string
  employee_name: string
  date: string
  check_in: string | null
  check_out: string | null
  status: 'present' | 'late' | 'absent' | 'half_day' | 'on_leave'
  check_in_confidence: number | null
  check_out_confidence: number | null
  source: 'cctv' | 'manual' | 'webcam' | 'mobile'
  latitude?: string | number | null
  longitude?: string | number | null
  notes: string
  overtime_minutes?: number
  early_leave?: boolean
  missing_checkout?: boolean
  created_at: string
  updated_at: string
}

export interface DashboardSummary {
  date: string
  from?: string
  to?: string
  summary: {
    total_employees: number
    trained_faces: number
    present_today: number
    late_today: number
    absent_today: number
    checked_out_today: number
    half_day_today?: number
    on_leave_today?: number
    review_pending?: number
    unknown_today?: number
    spoof_today?: number
    recognized_today?: number
    anomaly_open?: number
    cameras?: {
      total: number
      online: number
      degraded: number
      offline: number
      stopped: number
    }
    visitors_on_site?: number
    visitors_expected?: number
  }
  workday?: { is_workday: boolean; reason: string }
  department_stats: Array<{
    department: string
    total: number
    present_count: number
    late_count: number
  }>
  charts?: {
    trend: Array<{
      date: string
      is_workday: boolean
      present: number
      late: number
      half_day: number
      on_leave: number
      absent: number
    }>
    hourly: Array<{ hour: number; count: number }>
    sources: Array<{ source: string; count: number }>
    branches: Array<{ branch: string; total: number; present_count: number; late_count: number }>
    ai_trend: Array<{ date: string; recognized: number; unknown: number; spoof: number; anomaly: number }>
  }
  recent_activity: AttendanceRecord[]
}

export interface DailyReport {
  date: string
  workday?: { is_workday: boolean; reason: string; holiday?: string | null }
  attendance: AttendanceRecord[]
  absent: Array<{ employee_id: string; name: string; department: string }>
  on_leave?: Array<{ employee_id: string; name: string; department: string; leave_type: string }>
  totals: { present: number; late: number; absent: number; half_day?: number; on_leave?: number }
}

export interface RangeReport {
  from: string
  to: string
  people_count: number
  days: Array<{
    date: string
    is_workday: boolean
    reason: string
    present: number
    late: number
    half_day: number
    on_leave: number
    absent: number
    overtime_minutes: number
  }>
  totals: {
    present: number
    late: number
    absent: number
    half_day: number
    on_leave: number
    overtime_minutes: number
  }
  exceptions: Array<{
    date: string
    employee_id: string
    name: string
    kind: string
    minutes?: number
  }>
}

export interface PortalStatus {
  date: string
  role: string
  people: Array<{
    employee_id: string
    employee_pk: number
    name: string
    department: string
    designation: string
    status: string
    workday: { is_workday: boolean; reason: string }
    shift: { name: string; start_time: string; late_after: string; end_time: string }
    check_in: string | null
    check_out: string | null
    early_leave: boolean
    overtime_minutes: number
    notes: string
    leave_type: string | null
  }>
  recent: Array<{
    employee_id: string
    days: Array<{ date: string; status: string; check_in: string | null; check_out: string | null }>
  }>
}

export interface PunchGeofence {
  enabled: boolean
  latitude: number | null
  longitude: number | null
  radius_m: number | null
  branch_name: string
  distance_m?: number | null
  inside?: boolean
}

export interface PortalPunchContext {
  employee_id: string
  employee_name: string
  trained: boolean
  geofence: PunchGeofence
}

export interface PortalPunchResult {
  matched: boolean
  employee_id: string
  confidence: number
  geofence: PunchGeofence
  attendance: {
    action: string
    message: string
    date: string
    check_in: string | null
    check_out: string | null
    status: string
    source: string
  }
}

export interface Holiday {
  id: number
  date: string
  name: string
  repeats_yearly: boolean
  branch?: number | null
  branch_name?: string | null
  created_at: string
}

export interface LeaveRequest {
  id: number
  employee: number
  employee_id: string
  employee_name: string
  leave_type: string
  start_date: string
  end_date: string
  status: 'pending' | 'approved' | 'rejected'
  reason: string
  decided_by_email: string | null
  created_at: string
  updated_at: string
}

export interface MatchReview {
  id: number
  employee_id: string | null
  employee_name: string
  suggested_employee_id: string
  camera_id: number | null
  camera_name: string
  image_url: string
  confidence: number
  second_best: number | null
  reason: 'low_confidence' | 'ambiguous'
  status: 'pending' | 'confirmed' | 'rejected'
  track_id: number | null
  source: string
  notes: string
  reviewed_by_email: string | null
  reviewed_at: string | null
  attendance_action: string
  detected_at: string
}

export interface GalleryStats {
  total_employees_with_enrollment: number
  enrolled: number
  trained: number
  ready_for_recognition: number
}

export interface EnrollmentDetail {
  id: number
  employee_id: string
  employee_name: string
  is_enrolled: boolean
  is_trained: boolean
  total_images: number
  model_version: string
  dataset_folder: string
  profile_image: string | null
  embeddings_count?: number
  created_at: string
  updated_at: string
}

export interface CaptureResult {
  accepted: boolean
  quality?: {
    passed: boolean
    message: string
    det_score?: number
    blur_score?: number
    face_area_ratio?: number
    liveness?: {
      passed: boolean
      skipped?: boolean
      score?: number | null
      message: string
    }
  }
  total_images?: number
  images_required?: number
  is_enrolled?: boolean
  error?: string
}

export interface IdentifyResult {
  matched: boolean
  employee_id?: string
  confidence: number
  message: string
  ambiguous?: boolean
  liveness?: {
    passed: boolean
    skipped?: boolean
    score?: number | null
    message: string
  }
  attendance?: {
    action: string
    message: string
    date: string | null
    check_in: string | null
    check_out: string | null
    status: string
    hits?: number
    required?: number
  }
}

export interface CameraRuntime {
  camera_id: number
  name: string
  organization_id?: number | null
  zone?: string
  running: boolean
  connected: boolean
  last_error: string
  last_frame_at: string | null
  frames_processed: number
  gallery_size?: number
  fps?: number
  health?: string
  active_tracks?: number
  recent_events: CCTVEvent[]
  has_snapshot: boolean
}

export type CameraZone = 'mixed' | 'entry' | 'exit' | 'interior'

export interface Camera {
  id: number
  name: string
  location: string
  branch?: number | null
  branch_name?: string | null
  rtsp_url?: string
  zone: CameraZone
  is_active: boolean
  sort_order: number
  health?: 'online' | 'degraded' | 'offline' | 'stopped'
  health_status?: 'online' | 'degraded' | 'offline' | 'stopped'
  last_heartbeat_at?: string | null
  last_error?: string
  fps?: number | null
  runtime: CameraRuntime | null
  created_at: string
  updated_at: string
}

export interface CameraFormData {
  name: string
  location: string
  branch?: number | null
  rtsp_url: string
  zone: CameraZone
  is_active: boolean
  sort_order: number
}

export interface CCTVEvent {
  time: string
  camera_id: number
  camera_name: string
  matched: boolean
  employee_id?: string | null
  confidence: number
  message: string
  snapshot?: DetectionSnapshot
  attendance?: {
    action: string
    message: string
    status: string
  }
  dwell_seconds?: number
}

export interface RecognitionEvent {
  id: number
  kind: 'recognized' | 'unknown' | 'spoof' | 'review' | 'anomaly' | 'camera'
  status: 'open' | 'dismissed' | 'assigned'
  employee_id?: string | null
  employee_name?: string
  camera_id?: number | null
  camera_name: string
  confidence: number
  message: string
  extra?: Record<string, unknown>
  image_url?: string
  track_id?: number | null
  source: string
  attendance_action?: string
  detected_at: string
}

export interface RecognitionReport {
  from: string
  to: string
  totals: {
    recognized: number
    unknown: number
    spoof: number
    review: number
    anomaly: number
    camera: number
  }
  days: Array<{ date: string; recognized: number; unknown: number; spoof: number; anomaly: number }>
  cameras: Array<{ camera_name: string; recognized: number; unknown: number; spoof: number }>
}

export interface DetectionSnapshot {
  id: number
  employee_id: string
  employee_name: string
  camera_id: number | null
  camera_name: string
  camera_label: string
  image_url: string
  confidence: number
  attendance_action: string
  detected_at: string
}

export interface CCTVOverview {
  cameras: Camera[]
  events: CCTVEvent[]
  snapshots?: DetectionSnapshot[]
  running_count: number
  camera_quota?: number
  dwell?: {
    active: CameraDwell[]
    today: Array<{ employee_id: string; employee_name: string; seconds: number }>
  }
}

export interface CameraDwell {
  id: number
  employee_id: string
  employee_name: string
  camera_id: number
  camera_name: string
  started_at: string
  last_seen_at: string
  ended_at: string | null
  seconds: number
  active: boolean
  confidence: number
}

export type OrgType = 'company' | 'school'
export type OrgRole = 'owner' | 'admin' | 'operator' | 'viewer' | 'employee' | 'parent'
export type PlanId = 'free' | 'starter' | 'pro'

export interface PlanLimits {
  label: string
  people: number | null
  cameras: number
  branches?: number
  staff: number | null
  webhooks: boolean
  api_key: boolean
  alerts?: boolean
  exports?: boolean
  self_service?: boolean
}

export interface Organization {
  id: number
  name: string
  slug: string
  org_type: OrgType
  timezone: string
  work_start: string
  late_after: string
  weekend_days?: number[]
  is_active: boolean
  plan: PlanId
  effective_plan: PlanId
  subscription_status: string
  current_period_end: string | null
  trial_ends_at: string | null
  trial_active: boolean
  limits: PlanLimits
  features: { webhooks: boolean; api_key: boolean; cctv: boolean; alerts?: boolean; exports?: boolean; self_service?: boolean }
  billing_exempt: boolean
  created_via: 'signup' | 'platform'
  webhook_url: string
  created_at: string
  updated_at: string
}

export interface AuthUser {
  id: number
  email: string
  first_name: string
  last_name: string
  role: OrgRole | 'superadmin' | null
  is_superadmin: boolean
  organization: Organization | null
  portal_people?: Array<{ id: number; employee_id: string; name: string }>
}

export interface AuthResponse extends AuthUser {
  access: string
  refresh: string
}

export interface Membership {
  id: number
  user_id?: number
  email: string
  username: string
  first_name: string
  last_name: string
  role: OrgRole
  created_at: string
}

export interface Invite {
  id: number
  email: string
  role: OrgRole
  token: string
  invited_by_email: string | null
  accepted_at: string | null
  expires_at: string
  created_at: string
  invite_url: string
}

export interface Integrations {
  webhook_url: string
  webhook_secret: string
  api_key: string
  can_use_webhooks: boolean
  can_use_api_key: boolean
  can_use_alerts?: boolean
  notify_late?: boolean
  notify_absent?: boolean
  notify_email?: boolean
  notify_sms?: boolean
  notify_whatsapp?: boolean
  twilio_account_sid?: string
  twilio_auth_token?: string
  twilio_from_number?: string
  twilio_whatsapp_from?: string
}

export interface BillingSummary {
  organization: Organization
  plans: Array<{ id: PlanId } & PlanLimits>
  stripe_configured: boolean
  has_stripe_customer: boolean
  billing_exempt: boolean
}

export interface PlatformOrganization {
  id: number
  name: string
  slug: string
  org_type: OrgType
  is_active: boolean
  plan: PlanId
  effective_plan: PlanId
  billing_exempt: boolean
  created_via: 'signup' | 'platform'
  subscription_status: string
  trial_ends_at: string | null
  people_count: number
  camera_count: number
  owner_email: string
  owner_name: string
  created_at: string
}

export interface PlatformOverview {
  organizations: PlatformOrganization[]
  plans: Array<{ id: PlanId } & PlanLimits>
  totals: {
    organizations: number
    active: number
    self_serve: number
    complimentary: number
  }
}

export interface PlatformDashboard {
  totals: {
    organizations: number
    active: number
    self_serve: number
    complimentary: number
    people: number
    cameras: number
  }
  by_plan: Array<{ plan: PlanId; total: number }>
  plans: Array<{ id: PlanId } & PlanLimits>
  recent: PlatformOrganization[]
  stripe_configured: boolean
}

export interface PlatformSettings {
  trial_days: number
  superadmin_email: string
  stripe_configured: boolean
  frontend_url: string
}

export interface PayrollPolicy {
  currency: string
  pay_frequency: 'monthly' | 'biweekly' | 'weekly'
  working_days_per_month: string
  hours_per_day: string
  annual_leave_days: number
  sick_leave_days: number
  other_leave_days: number
  annual_leave_paid: boolean
  sick_leave_paid: boolean
  other_leave_paid: boolean
  unpaid_leave_allowed: boolean
  leave_year_start_month: number
  carry_forward_annual: boolean
  carry_forward_max_days: number
  probation_months: number
  probation_blocks_annual: boolean
  enforce_leave_balance: boolean
  holiday_paid: boolean
  weekend_paid: boolean
  absent_deduct: boolean
  half_day_pay_factor: string
  late_count_free: number
  late_penalty_mode: 'none' | 'fixed' | 'quarter_day'
  late_penalty_amount: string
  early_leave_deduct: boolean
  early_leave_as_half_day: boolean
  overtime_paid: boolean
  overtime_multiplier: string
            overtime_min_minutes: number
            overtime_requires_approval: boolean
            tax_percent: string
  provident_fund_percent: string
  updated_at?: string
}

export interface EmployeeCompensation {
  employee_id: string
  employee_name: string
  department?: string
  designation?: string
  is_active?: boolean
  pay_type: 'monthly' | 'daily' | 'hourly'
  basic_salary: string
  housing_allowance: string
  transport_allowance: string
  medical_allowance: string
  other_allowance: string
  other_deduction: string
  hire_date: string | null
  bank_name: string
  account_title: string
  account_number: string
  notes: string
  gross?: string
  salary_set?: boolean
  updated_at?: string
}

export interface LeaveBalanceRow {
  type: string
  label: string
  entitled: number | null
  used: number
  remaining: number | null
  paid: boolean
}

export interface LeaveBalance {
  employee_id: string
  employee_pk: number
  name: string
  year_start: string
  year_end: string
  in_probation: boolean
  balances: Record<string, LeaveBalanceRow>
}

export interface Payslip {
  id: number
  employee_id: string
  employee_name: string
  department: string
  period_start?: string
  period_end?: string
  run_status?: string
  pay_type: string
  working_days: string
  present_days: string
  late_days: number
  half_days: number
  absent_days: string
  paid_leave_days: string
  unpaid_leave_days: string
  overtime_minutes: number
  early_leave_days: number
  basic_pay: string
  allowances: string
  overtime_pay: string
  absent_deduction: string
  late_deduction: string
  unpaid_leave_deduction: string
  half_day_deduction: string
  early_leave_deduction: string
  tax: string
  provident_fund: string
  other_deduction: string
  gross_pay: string
  total_deductions: string
  net_pay: string
  breakdown: {
    currency?: string
    daily_rate?: string
    hourly_rate?: string
    extra_lates?: number
    billable_overtime_minutes?: number
    bank_name?: string
    account_title?: string
    account_number?: string
  }
}

export interface PayrollRun {
  id: number
  period_start: string
  period_end: string
  status: 'draft' | 'finalized'
  notes: string
  warnings: string[]
  created_by_email: string | null
  finalized_by_email: string | null
  finalized_at: string | null
  created_at: string
  updated_at: string
  payslip_count: number
  totals: { gross: string; deductions: string; net: string }
  payslips?: Payslip[]
}

export interface ExitPolicy {
  notice_period_days: number
  probation_notice_days: number
  require_clearance: boolean
  require_interview: boolean
  auto_deactivate: boolean
  allow_notice_buyout: boolean
  updated_at?: string
}

export interface ExitChecklistTemplate {
  id: number
  category: 'it' | 'finance' | 'hr' | 'access' | 'assets' | 'other'
  title: string
  sort_order: number
  is_active: boolean
}

export interface ExitClearanceItem {
  id: number
  category: string
  title: string
  is_cleared: boolean
  notes: string
  cleared_by_email: string | null
  cleared_at: string | null
  sort_order: number
}

export type ExitType = 'resignation' | 'termination' | 'contract_end' | 'retirement' | 'absconding'
export type ExitStatus = 'initiated' | 'in_progress' | 'completed' | 'cancelled'

export interface ExitCase {
  id: number
  employee: number
  employee_id: string
  employee_name: string
  department: string
  exit_type: ExitType
  status: ExitStatus
  resignation_date: string
  last_working_day: string
  notice_period_days: number
  notice_buyout_days: number
  notice_shortfall_days: number
  reason: string
  handover_notes: string
  interview_notes: string
  interview_completed: boolean
  rehire_eligible: boolean
  clearance_done: boolean
  checklist_items: ExitClearanceItem[]
  initiated_by_email: string | null
  final_settlement_notes?: string
  last_payroll_run?: number | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface LeaveType {
  id: number
  code: string
  name: string
  paid: boolean
  entitlement_days: number
  requires_document: boolean
  is_active: boolean
  sort_order: number
}

export interface ApprovalStep {
  id?: number
  order: number
  assignee_role: 'manager' | 'admin' | 'owner'
}

export interface ApprovalWorkflow {
  id: number
  kind: 'leave' | 'overtime' | 'attendance_correction' | 'exit'
  is_active: boolean
  steps: ApprovalStep[]
  updated_at?: string
}

export interface ApprovalRequest {
  id: number
  kind: string
  kind_label: string
  target_id: number
  employee: number
  employee_id: string
  employee_name: string
  status: 'pending' | 'approved' | 'rejected' | 'cancelled'
  current_step_role: string | null
  submitted_by_email: string | null
  can_act: boolean
  created_at: string
  decided_at: string | null
}

export interface AttendanceCorrection {
  id: number
  employee: number
  employee_id: string
  employee_name: string
  date: string
  requested_check_in: string | null
  requested_check_out: string | null
  original_check_in: string | null
  original_check_out: string | null
  original_status: string
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  decided_by_email: string | null
  applied_at: string | null
  created_at: string
}

export interface OvertimeRequest {
  id: number
  employee: number
  employee_id: string
  employee_name: string
  date: string
  minutes: number
  reason: string
  source: string
  status: 'pending' | 'approved' | 'rejected'
  decided_by_email: string | null
  created_at: string
}

export interface InAppNotification {
  id: number
  kind: string
  title: string
  body: string
  link: string
  read_at: string | null
  created_at: string
}

export type VisitorIdType = 'cnic' | 'passport' | 'license' | 'other'
export type VisitPurpose = 'meeting' | 'interview' | 'delivery' | 'contractor' | 'parent' | 'vendor' | 'other'
export type VisitStatus = 'expected' | 'checked_in' | 'checked_out' | 'cancelled' | 'no_show' | 'denied'
export type VisitSource = 'walkin' | 'preregister'

export interface Visitor {
  id: number
  first_name: string
  last_name: string
  full_name: string
  phone: string
  email: string
  company: string
  id_type: VisitorIdType
  id_number: string
  photo_url?: string
  notes: string
  is_blacklisted: boolean
  blacklist_reason: string
  visit_count?: number
  created_at: string
  updated_at: string
}

export interface Visit {
  id: number
  visitor: number
  visitor_detail: Visitor
  host: number | null
  host_name: string
  host_employee_id: string | null
  branch: number | null
  branch_name: string | null
  purpose: VisitPurpose
  purpose_label: string
  status: VisitStatus
  status_label: string
  source: VisitSource
  expected_at: string | null
  expected_end: string | null
  check_in_at: string | null
  check_out_at: string | null
  badge_code: string
  vehicle_plate: string
  notes: string
  public_token: string
  denied_reason: string
  gate_path: string
  created_at: string
  updated_at: string
}

export interface VisitSummary {
  date: string
  on_site: number
  expected_today: number
  checked_in_today: number
  watchlist: number
}

export interface PublicVisit {
  visitor_name: string
  visitor_company: string
  host_name: string
  organization_name: string
  purpose_label: string
  status: VisitStatus
  status_label: string
  expected_at: string | null
  expected_end: string | null
  check_in_at: string | null
  badge_code: string
  branch_name: string | null
}

export interface VisitWritePayload {
  first_name?: string
  last_name?: string
  phone?: string
  email?: string
  company?: string
  id_type?: VisitorIdType
  id_number?: string
  visitor?: number
  host?: number | null
  branch?: number | null
  purpose?: VisitPurpose
  source?: VisitSource
  expected_at?: string | null
  expected_end?: string | null
  vehicle_plate?: string
  notes?: string
  check_in_now?: boolean
}

export interface HrReport {
  from: string
  to: string
  headcount: {
    active: number
    total: number
    by_branch: Record<string, number>
    by_department: Record<string, number>
    by_employment_type: Record<string, number>
  }
  joiners: Array<{ employee_id: string; name: string; joining_date: string; branch: string }>
  leave_utilization: Record<string, number>
  overtime_minutes: number
  approved_overtime_minutes: number
  exits: Array<{ employee_id: string; name: string; exit_type: string; last_working_day: string }>
}

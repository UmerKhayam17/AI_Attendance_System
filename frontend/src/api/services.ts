import {
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  apiPostForm,
  apiPublicGet,
  apiPublicPost,
  apiPut,
} from './client'
import type {
  AttendanceRecord,
  AuthResponse,
  AuthUser,
  BillingSummary,
  Branch,
  CaptureResult,
  CCTVOverview,
  Camera,
  CameraFormData,
  DailyReport,
  DashboardSummary,
  Department,
  DetectionSnapshot,
  Employee,
  EmployeeDocument,
  EmployeeFormData,
  EnrollmentDetail,
  GalleryStats,
  Holiday,
  IdentifyResult,
  Integrations,
  Invite,
  LeaveRequest,
  MatchReview,
  Membership,
  Organization,
  PayrollPolicy,
  PayrollRun,
  EmployeeCompensation,
  LeaveBalance,
  LeaveType,
  ExitPolicy,
  ExitCase,
  ExitChecklistTemplate,
  PlanId,
  PlanLimits,
  PlatformDashboard,
  PlatformOrganization,
  PlatformOverview,
  PlatformSettings,
  PortalStatus,
  PortalPunchContext,
  PortalPunchResult,
  RangeReport,
  RecognitionEvent,
  RecognitionReport,
  ApprovalRequest,
  ApprovalWorkflow,
  AttendanceCorrection,
  OvertimeRequest,
  InAppNotification,
  HrReport,
  Shift,
  ShiftAssignment,
  Payslip,
  PublicVisit,
  Visit,
  Visitor,
  VisitSummary,
  VisitWritePayload,
} from '../types'

const BASE = '/api'

export const authApi = {
  signup: (data: {
    email: string
    password: string
    first_name: string
    last_name?: string
    organization_name: string
    org_type: 'company' | 'school'
  }) => apiPost<AuthResponse>(`${BASE}/auth/signup/`, data),
  login: (email: string, password: string) =>
    apiPost<AuthResponse>(`${BASE}/auth/login/`, { email, password }),
  me: () => apiGet<AuthUser>(`${BASE}/auth/me/`),
  passwordReset: (email: string) => apiPost<{ detail: string; debug_link?: string }>(`${BASE}/auth/password-reset/`, { email }),
  passwordResetConfirm: (uid: string, token: string, password: string) =>
    apiPost(`${BASE}/auth/password-reset/confirm/`, { uid, token, password }),
  invitePreview: (token: string) =>
    apiGet<{ email: string; role: string; organization: Organization }>(
      `${BASE}/auth/invite/?token=${encodeURIComponent(token)}`,
    ),
  acceptInvite: (data: { token: string; password: string; first_name: string; last_name?: string }) =>
    apiPost<AuthResponse>(`${BASE}/auth/invite/accept/`, data),
}

export const platformApi = {
  dashboard: () => apiGet<PlatformDashboard>(`${BASE}/platform/dashboard/`),
  plans: () => apiGet<{ plans: Array<{ id: PlanId } & PlanLimits> }>(`${BASE}/platform/plans/`),
  savePlans: (plans: Array<{ id: PlanId } & PlanLimits>) =>
    apiPut<{ plans: Array<{ id: PlanId } & PlanLimits> }>(`${BASE}/platform/plans/`, { plans }),
  settings: () => apiGet<PlatformSettings>(`${BASE}/platform/settings/`),
  updateSettings: (data: {
    trial_days?: number
    current_password?: string
    new_password?: string
  }) => apiPatch<PlatformSettings>(`${BASE}/platform/settings/`, data),
  list: () => apiGet<PlatformOverview>(`${BASE}/platform/organizations/`),
  create: (data: {
    name: string
    org_type: 'company' | 'school'
    plan: PlanId
    billing_exempt: boolean
    owner_email: string
    owner_password: string
    owner_first_name: string
    owner_last_name?: string
  }) => apiPost<PlatformOrganization>(`${BASE}/platform/organizations/`, data),
  update: (
    id: number,
    data: Partial<{ name: string; is_active: boolean; plan: PlanId; billing_exempt: boolean }>,
  ) => apiPatch<PlatformOrganization>(`${BASE}/platform/organizations/${id}/`, data),
}

export const orgApi = {
  get: () => apiGet<Organization>(`${BASE}/org/`),
  update: (data: Partial<Pick<Organization, 'name' | 'org_type' | 'timezone' | 'work_start' | 'late_after' | 'weekend_days'>>) =>
    apiPatch<Organization>(`${BASE}/org/`, data),
  members: () => apiGet<Membership[]>(`${BASE}/org/members/`),
  updateMember: (id: number, role: string) => apiPatch<Membership>(`${BASE}/org/members/${id}/`, { role }),
  removeMember: (id: number) => apiDelete(`${BASE}/org/members/${id}/`),
  invites: () => apiGet<Invite[]>(`${BASE}/org/invites/`),
  invite: (email: string, role: string) => apiPost<Invite>(`${BASE}/org/invites/`, { email, role }),
  revokeInvite: (id: number) => apiDelete(`${BASE}/org/invites/${id}/`),
  integrations: () => apiGet<Integrations>(`${BASE}/org/integrations/`),
  updateIntegrations: (data: Partial<Integrations>) =>
    apiPatch<Integrations>(`${BASE}/org/integrations/`, data),
  rotateKey: () => apiPost<Integrations>(`${BASE}/org/integrations/rotate-key/`),
  branches: () => apiGet<Branch[]>(`${BASE}/org/branches/`),
  createBranch: (data: Partial<Branch>) => apiPost<Branch>(`${BASE}/org/branches/`, data),
  updateBranch: (id: number, data: Partial<Branch>) => apiPatch<Branch>(`${BASE}/org/branches/${id}/`, data),
  deleteBranch: (id: number) => apiDelete(`${BASE}/org/branches/${id}/`),
  shifts: (branch?: number) =>
    apiGet<Shift[]>(`${BASE}/org/shifts/${branch ? `?branch=${branch}` : ''}`),
  createShift: (data: {
    name: string
    start_time: string
    late_after: string
    end_time: string
    kind?: string
    branch?: number | null
    required_hours?: number | null
    break_start?: string | null
    break_end?: string | null
    second_start?: string | null
    second_end?: string | null
    grace_minutes?: number
    early_leave_grace_minutes?: number
    overtime_grace_minutes?: number
    is_default?: boolean
    is_active?: boolean
  }) => apiPost<Shift>(`${BASE}/org/shifts/`, data),
  updateShift: (
    id: number,
    data: Partial<{
      name: string
      start_time: string
      late_after: string
      end_time: string
      kind: string
      branch: number | null
      required_hours: number | null
      break_start: string | null
      break_end: string | null
      second_start: string | null
      second_end: string | null
      grace_minutes: number
      early_leave_grace_minutes: number
      overtime_grace_minutes: number
      is_default: boolean
      is_active: boolean
    }>,
  ) => apiPatch<Shift>(`${BASE}/org/shifts/${id}/`, data),
  deleteShift: (id: number) => apiDelete(`${BASE}/org/shifts/${id}/`),
  departments: (branch?: number) =>
    apiGet<Department[]>(`${BASE}/org/departments/${branch ? `?branch=${branch}` : ''}`),
  createDepartment: (data: { name: string; branch?: number | null; is_active?: boolean; sort_order?: number }) =>
    apiPost<Department>(`${BASE}/org/departments/`, data),
  updateDepartment: (
    id: number,
    data: Partial<{ name: string; branch: number | null; is_active: boolean; sort_order: number }>,
  ) => apiPatch<Department>(`${BASE}/org/departments/${id}/`, data),
  deleteDepartment: (id: number) => apiDelete(`${BASE}/org/departments/${id}/`),
  leaveTypes: () => apiGet<LeaveType[]>(`${BASE}/org/leave-types/`),
  createLeaveType: (data: Partial<LeaveType>) => apiPost<LeaveType>(`${BASE}/org/leave-types/`, data),
  updateLeaveType: (id: number, data: Partial<LeaveType>) => apiPatch<LeaveType>(`${BASE}/org/leave-types/${id}/`, data),
}

export const billingApi = {
  summary: () => apiGet<BillingSummary>(`${BASE}/billing/`),
  checkout: (plan: 'starter' | 'pro') => apiPost<{ url: string }>(`${BASE}/billing/checkout/`, { plan }),
  portal: () => apiPost<{ url: string }>(`${BASE}/billing/portal/`),
}

export const employeeApi = {
  list: () => apiGet<Employee[]>(`${BASE}/employees/`),
  get: (id: string) => apiGet<Employee>(`${BASE}/employees/${id}/`),
  create: (data: EmployeeFormData) => apiPost<Employee>(`${BASE}/employees/`, data),
  update: (id: string, data: Partial<EmployeeFormData>) =>
    apiPatch<Employee>(`${BASE}/employees/${id}/`, data),
  replace: (id: string, data: EmployeeFormData) =>
    apiPut<Employee>(`${BASE}/employees/${id}/`, data),
  remove: (id: string) => apiDelete(`${BASE}/employees/${id}/`),
  activate: (id: string) => apiPost<Employee>(`${BASE}/employees/${id}/activate/`),
  deactivate: (id: string) => apiPost<Employee>(`${BASE}/employees/${id}/deactivate/`),
  invitePortal: (id: string, data: { role: 'employee' | 'parent'; email?: string }) =>
    apiPost<Invite>(`${BASE}/employees/${id}/invite-portal/`, data),
  documents: (id: string) => apiGet<EmployeeDocument[]>(`${BASE}/employees/${id}/documents/`),
  uploadDocument: (id: string, data: FormData) =>
    apiPostForm<EmployeeDocument>(`${BASE}/employees/${id}/documents/`, data),
  deleteDocument: (id: string, docId: number) =>
    apiDelete(`${BASE}/employees/${id}/documents/${docId}/`),
  shiftAssignments: (id: string) =>
    apiGet<ShiftAssignment[]>(`${BASE}/employees/${id}/shift-assignments/`),
  createShiftAssignment: (
    id: string,
    data: { shift: number; start_date: string; end_date?: string | null; weekdays?: number[] },
  ) => apiPost<ShiftAssignment>(`${BASE}/employees/${id}/shift-assignments/`, data),
  deleteShiftAssignment: (id: string, assignmentId: number) =>
    apiDelete(`${BASE}/employees/${id}/shift-assignments/${assignmentId}/`),
}

export const recognitionApi = {
  galleryStats: () => apiGet<GalleryStats>(`${BASE}/recognition/gallery/stats/`),
  enrollmentStatus: (employeeId: string) =>
    apiGet<EnrollmentDetail>(`${BASE}/recognition/enroll/${employeeId}/`),
  capture: (employeeId: string, image: string) =>
    apiPost<CaptureResult>(`${BASE}/recognition/enroll/${employeeId}/capture/`, { image }),
  train: (employeeId: string) =>
    apiPost<{ trained: boolean; images_used: number; enrollment: EnrollmentDetail }>(
      `${BASE}/recognition/enroll/${employeeId}/train/`,
    ),
  identify: (image: string, markAttendance = false, source = 'webcam') =>
    apiPost<IdentifyResult>(`${BASE}/recognition/identify/`, {
      image,
      mark_attendance: markAttendance,
      source,
    }),
  cameras: () => apiGet<Camera[]>(`${BASE}/recognition/cameras/`),
  createCamera: (data: CameraFormData) => apiPost<Camera>(`${BASE}/recognition/cameras/`, data),
  updateCamera: (id: number, data: Partial<CameraFormData>) =>
    apiPatch<Camera>(`${BASE}/recognition/cameras/${id}/`, data),
  deleteCamera: (id: number) => apiDelete(`${BASE}/recognition/cameras/${id}/`),
  cctvOverview: () => apiGet<CCTVOverview>(`${BASE}/recognition/cctv/`),
  cctvStartAll: () => apiPost<{ action: string; statuses: unknown[] }>(`${BASE}/recognition/cctv/`, { action: 'start_all' }),
  cctvStopAll: () => apiPost<{ action: string; statuses: unknown[] }>(`${BASE}/recognition/cctv/`, { action: 'stop_all' }),
  cameraStart: (id: number) => apiPost(`${BASE}/recognition/cameras/${id}/start/`),
  cameraStop: (id: number) => apiPost(`${BASE}/recognition/cameras/${id}/stop/`),
  cameraSnapshotUrl: (id: number) => `${BASE}/recognition/cameras/${id}/snapshot/?t=${Date.now()}`,
  detections: (params?: { camera_id?: number; employee_id?: string; limit?: number }) => {
    const query = new URLSearchParams()
    if (params?.camera_id) query.set('camera_id', String(params.camera_id))
    if (params?.employee_id) query.set('employee_id', params.employee_id)
    if (params?.limit) query.set('limit', String(params.limit))
    const qs = query.toString()
    return apiGet<{ snapshots: DetectionSnapshot[] }>(
      `${BASE}/recognition/detections/${qs ? `?${qs}` : ''}`,
    )
  },
  events: (params?: { kind?: string; status?: string; camera?: number; date?: string }) => {
    const query = new URLSearchParams()
    if (params?.kind) query.set('kind', params.kind)
    if (params?.status) query.set('status', params.status)
    if (params?.camera) query.set('camera', String(params.camera))
    if (params?.date) query.set('date', params.date)
    const qs = query.toString()
    return apiGet<RecognitionEvent[]>(`${BASE}/recognition/events/${qs ? `?${qs}` : ''}`)
  },
  dismissEvent: (id: number) => apiPost<RecognitionEvent>(`${BASE}/recognition/events/${id}/dismiss/`),
  dismissAllEvents: (params?: { kind?: string; status?: string; date?: string }) => {
    const query = new URLSearchParams()
    if (params?.kind) query.set('kind', params.kind)
    if (params?.status) query.set('status', params.status)
    if (params?.date) query.set('date', params.date)
    const qs = query.toString()
    return apiPost<{ dismissed: number }>(`${BASE}/recognition/events/dismiss_all/${qs ? `?${qs}` : ''}`)
  },
  assignEvent: (id: number, employeeId: string) =>
    apiPost<RecognitionEvent & { attendance?: { action: string; message: string; status: string } }>(
      `${BASE}/recognition/events/${id}/assign/`,
      { employee_id: employeeId },
    ),
}

export const attendanceApi = {
  list: (params?: { employee_id?: string; date?: string; status?: string; branch?: number }) => {
    const query = new URLSearchParams()
    if (params?.employee_id) query.set('employee_id', params.employee_id)
    if (params?.date) query.set('date', params.date)
    if (params?.status) query.set('status', params.status)
    if (params?.branch) query.set('branch', String(params.branch))
    const qs = query.toString()
    return apiGet<AttendanceRecord[]>(`${BASE}/attendance/records/${qs ? `?${qs}` : ''}`)
  },
  manual: (employeeId: string, action: 'check_in' | 'check_out', notes = '') =>
    apiPost<AttendanceRecord>(`${BASE}/attendance/manual/`, {
      employee_id: employeeId,
      action,
      notes,
    }),
  holidays: (branch?: number) =>
    apiGet<Holiday[]>(`${BASE}/attendance/holidays/${branch ? `?branch=${branch}` : ''}`),
  createHoliday: (data: { date: string; name: string; repeats_yearly: boolean; branch?: number | null }) =>
    apiPost<Holiday>(`${BASE}/attendance/holidays/`, data),
  deleteHoliday: (id: number) => apiDelete(`${BASE}/attendance/holidays/${id}/`),
  leave: (status?: string) => {
    const qs = status ? `?status=${status}` : ''
    return apiGet<LeaveRequest[]>(`${BASE}/attendance/leave/${qs}`)
  },
  createLeave: (data: {
    employee: number
    leave_type: string
    start_date: string
    end_date: string
    reason?: string
  }) => apiPost<LeaveRequest>(`${BASE}/attendance/leave/`, data),
  approveLeave: (id: number) => apiPost<LeaveRequest>(`${BASE}/attendance/leave/${id}/approve/`),
  rejectLeave: (id: number) => apiPost<LeaveRequest>(`${BASE}/attendance/leave/${id}/reject/`),
  corrections: () => apiGet<AttendanceCorrection[]>(`${BASE}/attendance/corrections/`),
  createCorrection: (data: {
    employee: number
    date: string
    requested_check_in?: string | null
    requested_check_out?: string | null
    reason?: string
  }) => apiPost<AttendanceCorrection>(`${BASE}/attendance/corrections/`, data),
  approveCorrection: (id: number) => apiPost<AttendanceCorrection>(`${BASE}/attendance/corrections/${id}/approve/`),
  rejectCorrection: (id: number) => apiPost<AttendanceCorrection>(`${BASE}/attendance/corrections/${id}/reject/`),
  overtime: () => apiGet<OvertimeRequest[]>(`${BASE}/attendance/overtime/`),
  createOvertime: (data: { employee: number; date: string; minutes: number; reason?: string }) =>
    apiPost<OvertimeRequest>(`${BASE}/attendance/overtime/`, data),
  approveOvertime: (id: number) => apiPost<OvertimeRequest>(`${BASE}/attendance/overtime/${id}/approve/`),
  rejectOvertime: (id: number) => apiPost<OvertimeRequest>(`${BASE}/attendance/overtime/${id}/reject/`),
}

export const reviewApi = {
  list: (status = 'pending') => apiGet<MatchReview[]>(`${BASE}/recognition/reviews/?status=${status}`),
  confirm: (id: number, employeeId?: string) =>
    apiPost<MatchReview & { attendance?: { action: string; message: string; status: string } }>(
      `${BASE}/recognition/reviews/${id}/confirm/`,
      employeeId ? { employee_id: employeeId } : {},
    ),
  reject: (id: number) => apiPost<MatchReview>(`${BASE}/recognition/reviews/${id}/reject/`),
}

export const dashboardApi = {
  summary: (branch?: number, from?: string, to?: string) => {
    const query = new URLSearchParams()
    if (branch) query.set('branch', String(branch))
    if (from) query.set('from', from)
    if (to) query.set('to', to)
    const qs = query.toString()
    return apiGet<DashboardSummary>(`${BASE}/dashboard/summary/${qs ? `?${qs}` : ''}`)
  },
  dailyReport: (date?: string, branch?: number) => {
    const query = new URLSearchParams()
    if (date) query.set('date', date)
    if (branch) query.set('branch', String(branch))
    const qs = query.toString()
    return apiGet<DailyReport>(`${BASE}/dashboard/daily-report/${qs ? `?${qs}` : ''}`)
  },
  rangeReport: (from: string, to: string, branch?: number) => {
    const query = new URLSearchParams({ from, to })
    if (branch) query.set('branch', String(branch))
    return apiGet<RangeReport>(`${BASE}/dashboard/range-report/?${query}`)
  },
  exportUrl: (from: string, to: string, format: 'xlsx' | 'csv' | 'pdf', branch?: number) => {
    const query = new URLSearchParams({ from, to, format })
    if (branch) query.set('branch', String(branch))
    return `${BASE}/dashboard/export/?${query}`
  },
  hrReport: (from: string, to: string, branch?: number) => {
    const query = new URLSearchParams({ from, to })
    if (branch) query.set('branch', String(branch))
    return apiGet<HrReport>(`${BASE}/dashboard/hr-report/?${query}`)
  },
  recognitionReport: (from: string, to: string, branch?: number) => {
    const query = new URLSearchParams({ from, to })
    if (branch) query.set('branch', String(branch))
    return apiGet<RecognitionReport>(`${BASE}/dashboard/recognition-report/?${query}`)
  },
}

export const payrollApi = {
  policy: () => apiGet<PayrollPolicy>(`${BASE}/payroll/policy/`),
  updatePolicy: (data: Partial<PayrollPolicy>) => apiPatch<PayrollPolicy>(`${BASE}/payroll/policy/`, data),
  defaultPeriod: () => apiGet<{ period_start: string; period_end: string }>(`${BASE}/payroll/period-default/`),
  leaveBalances: (employeeId?: string) => {
    const qs = employeeId ? `?employee_id=${encodeURIComponent(employeeId)}` : ''
    return apiGet<LeaveBalance[]>(`${BASE}/payroll/leave-balances/${qs}`)
  },
  compensation: (employeeId: string) => apiGet<EmployeeCompensation>(`${BASE}/payroll/compensation/${employeeId}/`),
  compensations: () => apiGet<EmployeeCompensation[]>(`${BASE}/payroll/compensation/`),
  updateCompensation: (employeeId: string, data: Partial<EmployeeCompensation>) =>
    apiPatch<EmployeeCompensation>(`${BASE}/payroll/compensation/${employeeId}/`, data),
  runs: () => apiGet<PayrollRun[]>(`${BASE}/payroll/runs/`),
  run: (id: number) => apiGet<PayrollRun>(`${BASE}/payroll/runs/${id}/`),
  generate: (period_start: string, period_end: string) =>
    apiPost<PayrollRun>(`${BASE}/payroll/runs/`, { period_start, period_end }),
  finalize: (id: number) => apiPost<PayrollRun>(`${BASE}/payroll/runs/${id}/finalize/`),
  deleteRun: (id: number) => apiDelete(`${BASE}/payroll/runs/${id}/`),
}

export const exitApi = {
  policy: () => apiGet<ExitPolicy>(`${BASE}/exits/policy/`),
  updatePolicy: (data: Partial<ExitPolicy>) => apiPatch<ExitPolicy>(`${BASE}/exits/policy/`, data),
  checklist: () => apiGet<ExitChecklistTemplate[]>(`${BASE}/exits/checklist/`),
  createChecklistItem: (data: Partial<ExitChecklistTemplate>) =>
    apiPost<ExitChecklistTemplate>(`${BASE}/exits/checklist/`, data),
  updateChecklistItem: (id: number, data: Partial<ExitChecklistTemplate>) =>
    apiPatch<ExitChecklistTemplate>(`${BASE}/exits/checklist/${id}/`, data),
  deleteChecklistItem: (id: number) => apiDelete(`${BASE}/exits/checklist/${id}/`),
  suggest: (employeeId: string, resignationDate?: string) => {
    const qs = new URLSearchParams({ employee_id: employeeId })
    if (resignationDate) qs.set('resignation_date', resignationDate)
    return apiGet<{ notice_period_days: number; last_working_day: string; in_probation: boolean }>(
      `${BASE}/exits/suggest/?${qs}`,
    )
  },
  cases: (status?: string) => {
    const qs = status ? `?status=${status}` : ''
    return apiGet<ExitCase[]>(`${BASE}/exits/cases/${qs}`)
  },
  case: (id: number) => apiGet<ExitCase>(`${BASE}/exits/cases/${id}/`),
  create: (data: {
    employee: number
    exit_type?: string
    resignation_date?: string
    last_working_day?: string
    notice_period_days?: number
    notice_buyout_days?: number
    reason?: string
    handover_notes?: string
  }) => apiPost<ExitCase>(`${BASE}/exits/cases/`, data),
  update: (id: number, data: Partial<ExitCase>) => apiPatch<ExitCase>(`${BASE}/exits/cases/${id}/`, data),
  complete: (id: number) => apiPost<ExitCase>(`${BASE}/exits/cases/${id}/complete/`),
  cancel: (id: number) => apiPost<ExitCase>(`${BASE}/exits/cases/${id}/cancel/`),
  toggleItem: (caseId: number, itemId: number, notes?: string) =>
    apiPost(`${BASE}/exits/cases/${caseId}/items/${itemId}/toggle/`, notes ? { notes } : {}),
}

export const portalApi = {
  status: (date?: string) => {
    const qs = date ? `?date=${date}` : ''
    return apiGet<PortalStatus>(`${BASE}/portal/status/${qs}`)
  },
  punchContext: () => apiGet<PortalPunchContext>(`${BASE}/portal/punch/`),
  punch: (data: { image: string; latitude: number; longitude: number }) =>
    apiPost<PortalPunchResult>(`${BASE}/portal/punch/`, data),
  leave: () => apiGet<LeaveRequest[]>(`${BASE}/portal/leave/`),
  createLeave: (data: {
    employee: number
    leave_type: string
    start_date: string
    end_date: string
    reason?: string
  }) => apiPost<LeaveRequest>(`${BASE}/portal/leave/`, data),
  balances: () => apiGet<LeaveBalance[]>(`${BASE}/portal/balances/`),
  corrections: () => apiGet<AttendanceCorrection[]>(`${BASE}/portal/corrections/`),
  createCorrection: (data: {
    employee: number
    date: string
    requested_check_in?: string | null
    requested_check_out?: string | null
    reason?: string
  }) => apiPost<AttendanceCorrection>(`${BASE}/portal/corrections/`, data),
  overtime: () => apiGet<OvertimeRequest[]>(`${BASE}/portal/overtime/`),
  createOvertime: (data: { employee: number; date: string; minutes: number; reason?: string }) =>
    apiPost<OvertimeRequest>(`${BASE}/portal/overtime/`, data),
  documents: () => apiGet<EmployeeDocument[]>(`${BASE}/portal/documents/`),
  payslips: () => apiGet<Payslip[]>(`${BASE}/portal/payslips/`),
  resignation: () => apiGet<ExitCase[]>(`${BASE}/portal/resignation/`),
  requestResignation: (data: { employee?: number; resignation_date?: string; reason?: string }) =>
    apiPost<ExitCase>(`${BASE}/portal/resignation/`, data),
}

export const approvalApi = {
  workflows: () => apiGet<ApprovalWorkflow[]>(`${BASE}/approvals/workflows/`),
  updateWorkflow: (id: number, data: Partial<ApprovalWorkflow> & { steps?: ApprovalWorkflow['steps'] }) =>
    apiPatch<ApprovalWorkflow>(`${BASE}/approvals/workflows/${id}/`, data),
  inbox: () => apiGet<ApprovalRequest[]>(`${BASE}/approvals/inbox/`),
  approve: (id: number, comment = '') => apiPost<ApprovalRequest>(`${BASE}/approvals/requests/${id}/approve/`, { comment }),
  reject: (id: number, comment = '') => apiPost<ApprovalRequest>(`${BASE}/approvals/requests/${id}/reject/`, { comment }),
  notifications: (unread = false) =>
    apiGet<InAppNotification[]>(`${BASE}/approvals/notifications/${unread ? '?unread=1' : ''}`),
  markRead: (id?: number) =>
    id
      ? apiPost(`${BASE}/approvals/notifications/${id}/read/`)
      : apiPost(`${BASE}/approvals/notifications/read/`),
}

export const visitorApi = {
  people: (params?: { watchlist?: boolean; q?: string }) => {
    const qs = new URLSearchParams()
    if (params?.watchlist) qs.set('watchlist', '1')
    if (params?.q) qs.set('q', params.q)
    const suffix = qs.toString() ? `?${qs}` : ''
    return apiGet<Visitor[]>(`${BASE}/visitors/people/${suffix}`)
  },
  updatePerson: (id: number, data: Partial<Visitor>) =>
    apiPatch<Visitor>(`${BASE}/visitors/people/${id}/`, data),
  watchlist: (id: number, blocked: boolean, reason = '') =>
    apiPost<Visitor>(`${BASE}/visitors/people/${id}/watchlist/`, { blocked, reason }),
  visits: (params?: { status?: string; date?: string; q?: string; branch?: number }) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.date) qs.set('date', params.date)
    if (params?.q) qs.set('q', params.q)
    if (params?.branch) qs.set('branch', String(params.branch))
    const suffix = qs.toString() ? `?${qs}` : ''
    return apiGet<Visit[]>(`${BASE}/visitors/visits/${suffix}`)
  },
  summary: (branch?: number) => {
    const qs = branch ? `?branch=${branch}` : ''
    return apiGet<VisitSummary>(`${BASE}/visitors/visits/summary/${qs}`)
  },
  create: (data: VisitWritePayload) => apiPost<Visit>(`${BASE}/visitors/visits/`, data),
  checkIn: (id: number) => apiPost<Visit>(`${BASE}/visitors/visits/${id}/check_in/`),
  checkOut: (id: number) => apiPost<Visit>(`${BASE}/visitors/visits/${id}/check_out/`),
  cancel: (id: number) => apiPost<Visit>(`${BASE}/visitors/visits/${id}/cancel/`),
  noShow: (id: number) => apiPost<Visit>(`${BASE}/visitors/visits/${id}/no_show/`),
  deny: (id: number, reason = '') =>
    apiPost<Visit>(`${BASE}/visitors/visits/${id}/deny/`, { reason }),
  gate: (token: string) => apiPublicGet<PublicVisit>(`${BASE}/visitors/gate/${token}/`),
  gateAction: (token: string, action: 'check_in' | 'check_out') =>
    apiPublicPost<PublicVisit>(`${BASE}/visitors/gate/${token}/`, { action }),
}

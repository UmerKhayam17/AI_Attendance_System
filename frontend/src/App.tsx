import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { GuestOnly, RequireAuth, RequireRole, RequireSuperAdmin, RequireTenant } from './auth/guards'
import { Layout } from './components/Layout'
import { ToastProvider } from './components/Toast'
import { isPortalRole } from './auth/roles'
import AcceptInvitePage from './pages/AcceptInvite'
import AttendancePage from './pages/Attendance'
import DashboardPage from './pages/Dashboard'
import EmployeesPage from './pages/Employees'
import EnrollmentPage from './pages/Enrollment'
import EventsPage from './pages/Events'
import VisitorGatePage from './pages/VisitorGate'
import VisitorsPage from './pages/Visitors'
import ExitsPage from './pages/Exits'
import ForgotPasswordPage from './pages/ForgotPassword'
import LeavePage from './pages/Leave'
import LoginPage from './pages/Login'
import MonitorPage from './pages/Monitor'
import MyStatusPage from './pages/MyStatus'
import PunchPage from './pages/Punch'
import PayrollPage from './pages/Payroll'
import SalariesPage from './pages/Salaries'
import CompaniesPage from './pages/platform/Companies'
import PlatformDashboardPage from './pages/platform/Dashboard'
import { PlatformLayout } from './pages/platform/PlatformLayout'
import PlatformPlansPage from './pages/platform/Plans'
import PlatformSettingsPage from './pages/platform/Settings'
import ReviewPage from './pages/Review'
import ReportsPage from './pages/Reports'
import ResetPasswordPage from './pages/ResetPassword'
import SignupPage from './pages/Signup'
import ApprovalSettingsPage from './pages/settings/ApprovalSettings'
import BillingSettingsPage from './pages/settings/BillingSettings'
import BranchSettingsPage from './pages/settings/BranchSettings'
import CalendarSettingsPage from './pages/settings/CalendarSettings'
import CameraSettingsPage from './pages/settings/CameraSettings'
import DepartmentSettingsPage from './pages/settings/DepartmentSettings'
import ExitSettingsPage from './pages/settings/ExitSettings'
import IntegrationsSettingsPage from './pages/settings/IntegrationsSettings'
import OrganizationSettingsPage from './pages/settings/OrganizationSettings'
import PayrollSettingsPage from './pages/settings/PayrollSettings'
import SettingsLayout from './pages/settings/SettingsLayout'
import SettingsOverviewPage from './pages/settings/SettingsOverview'
import ShiftSettingsPage from './pages/settings/ShiftSettings'
import TeamSettingsPage from './pages/settings/TeamSettings'

const STAFF_ROLES = ['owner', 'admin', 'operator', 'viewer'] as const

function HomePage() {
  const { role } = useAuth()
  if (isPortalRole(role)) return <MyStatusPage />
  return <DashboardPage />
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<GuestOnly />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
            </Route>
            <Route path="/accept-invite" element={<AcceptInvitePage />} />
            <Route path="/gate/:token" element={<VisitorGatePage />} />

            <Route element={<RequireAuth />}>
              <Route element={<RequireSuperAdmin />}>
                <Route path="platform" element={<PlatformLayout />}>
                  <Route index element={<PlatformDashboardPage />} />
                  <Route path="companies" element={<CompaniesPage />} />
                  <Route path="plans" element={<PlatformPlansPage />} />
                  <Route path="settings" element={<PlatformSettingsPage />} />
                </Route>
              </Route>
              <Route element={<RequireTenant />}>
              <Route element={<Layout />}>
                <Route index element={<HomePage />} />
                <Route element={<RequireRole roles={['employee', 'parent']} />}>
                  <Route path="me" element={<Navigate to="/" replace />} />
                  <Route path="me/leave" element={<MyStatusPage />} />
                  <Route path="me/corrections" element={<MyStatusPage />} />
                  <Route path="me/overtime" element={<MyStatusPage />} />
                  <Route path="me/documents" element={<MyStatusPage />} />
                  <Route path="me/payslips" element={<MyStatusPage />} />
                  <Route path="me/resign" element={<MyStatusPage />} />
                </Route>
                <Route element={<RequireRole roles={['employee']} />}>
                  <Route path="me/punch" element={<PunchPage />} />
                </Route>
                <Route element={<RequireRole roles={[...STAFF_ROLES]} />}>
                  <Route path="attendance" element={<AttendancePage />} />
                  <Route path="reports" element={<ReportsPage />} />
                  <Route path="visitors" element={<VisitorsPage />} />
                </Route>
                <Route element={<RequireRole roles={['owner', 'admin']} />}>
                  <Route path="employees" element={<EmployeesPage />} />
                  <Route path="salaries" element={<SalariesPage />} />
                  <Route path="leave" element={<LeavePage />} />
                  <Route path="payroll" element={<PayrollPage />} />
                  <Route path="exits" element={<ExitsPage />} />
                </Route>
                <Route element={<RequireRole roles={['owner', 'admin', 'operator']} />}>
                  <Route path="enrollment" element={<EnrollmentPage />} />
                  <Route path="monitor" element={<MonitorPage />} />
                  <Route path="review" element={<ReviewPage />} />
                  <Route path="events" element={<EventsPage />} />
                </Route>
                <Route element={<RequireRole roles={['owner', 'admin']} />}>
                  <Route path="settings" element={<SettingsLayout />}>
                    <Route index element={<SettingsOverviewPage />} />
                    <Route path="organization" element={<OrganizationSettingsPage />} />
                    <Route path="branches" element={<BranchSettingsPage />} />
                    <Route path="shifts" element={<ShiftSettingsPage />} />
                    <Route path="departments" element={<DepartmentSettingsPage />} />
                    <Route path="calendar" element={<CalendarSettingsPage />} />
                    <Route path="approvals" element={<ApprovalSettingsPage />} />
                    <Route path="payroll" element={<PayrollSettingsPage />} />
                    <Route path="exit" element={<ExitSettingsPage />} />
                    <Route path="team" element={<TeamSettingsPage />} />
                    <Route path="cameras" element={<CameraSettingsPage />} />
                    <Route path="integrations" element={<IntegrationsSettingsPage />} />
                    <Route element={<RequireRole roles={['owner']} />}>
                      <Route path="billing" element={<BillingSettingsPage />} />
                    </Route>
                  </Route>
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  )
}

import type { OrgRole, OrgType } from '../types'

export function orgLabels(orgType: OrgType | undefined) {
  if (orgType === 'school') {
    return {
      people: 'Students & Staff',
      person: 'Person',
      peopleNav: 'People Management',
      department: 'Class / Section',
      designation: 'Role',
      id: 'ID',
      branch: 'Campus',
      branches: 'Campuses',
    }
  }
  return {
    people: 'Employees',
    person: 'Employee',
    peopleNav: 'Employee Management',
    department: 'Department',
    designation: 'Designation',
    id: 'Employee ID',
    branch: 'Branch',
    branches: 'Branches',
  }
}

type AnyRole = OrgRole | 'superadmin' | null | undefined

export function canManagePeople(role: AnyRole) {
  return role === 'owner' || role === 'admin'
}

export function canOperate(role: AnyRole) {
  return role === 'owner' || role === 'admin' || role === 'operator'
}

export function canManageOrg(role: AnyRole) {
  return role === 'owner' || role === 'admin'
}

export function canBilling(role: AnyRole) {
  return role === 'owner'
}

export function isPortalRole(role: AnyRole) {
  return role === 'employee' || role === 'parent'
}

export function isStaffRole(role: AnyRole) {
  return role === 'owner' || role === 'admin' || role === 'operator' || role === 'viewer'
}

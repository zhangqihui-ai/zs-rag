import { http } from '../lib/http'
import type { MembershipInfo, MembershipRole, User } from '../stores/auth'

export interface UserDetail extends User {
  memberships: MembershipInfo[]
  is_bootstrap_admin: boolean
}

export interface UserCreatePayload {
  username: string
  email?: string | null
  password: string
  is_admin?: boolean
  space_assignments?: Array<{ enterprise_space_id: number; role: MembershipRole }>
}

export interface UserUpdatePayload {
  username?: string
  email?: string | null
  is_active?: boolean
  is_admin?: boolean
  password?: string
}

export async function listUsers(q?: string) {
  return http.get<UserDetail[]>('/users', { params: q ? { q } : undefined })
}

export async function getUser(userId: number) {
  return http.get<UserDetail>(`/users/${userId}`)
}

export async function createUser(payload: UserCreatePayload) {
  return http.post<UserDetail>('/users', payload)
}

export async function updateUser(userId: number, payload: UserUpdatePayload) {
  return http.patch<UserDetail>(`/users/${userId}`, payload)
}

export async function deleteUser(userId: number) {
  return http.delete(`/users/${userId}`)
}

export async function setUserMemberships(
  userId: number,
  assignments: Array<{ enterprise_space_id: number; role: MembershipRole }>,
) {
  return http.put<UserDetail>(`/users/${userId}/memberships`, { assignments })
}

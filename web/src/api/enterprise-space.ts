import { http } from '../lib/http'
import type { EnterpriseSpace, MembershipRole } from '../stores/auth'

export interface EnterpriseSpaceWithRole extends EnterpriseSpace {
  role: MembershipRole
}

export interface SpaceCreatePayload {
  name: string
  slug: string
  description?: string
}

export interface SpaceUpdatePayload {
  name?: string
  description?: string
}

export interface MembershipWithUser {
  id: number
  user_id: number
  enterprise_space_id: number
  role: MembershipRole
  created_at: string
  user: {
    id: number
    username: string
    email: string | null
    is_active: boolean
    is_admin: boolean
    created_at: string
    updated_at: string
  }
}

export async function listEnterpriseSpaces() {
  return http.get<EnterpriseSpaceWithRole[]>('/enterprise-spaces')
}

export async function listAllEnterpriseSpaces() {
  return http.get<EnterpriseSpace[]>('/enterprise-spaces/all')
}

export async function createEnterpriseSpace(payload: SpaceCreatePayload) {
  return http.post<EnterpriseSpace>('/enterprise-spaces', payload)
}

export async function updateEnterpriseSpace(spaceId: number, payload: SpaceUpdatePayload) {
  return http.patch<EnterpriseSpace>(`/enterprise-spaces/${spaceId}`, payload)
}

export async function deleteEnterpriseSpace(spaceId: number) {
  return http.delete(`/enterprise-spaces/${spaceId}`)
}

function spaceHeaders(spaceSlug?: string) {
  if (!spaceSlug) return undefined
  return { 'X-Enterprise-Space': spaceSlug }
}

export async function listSpaceMembers(spaceId: number, spaceSlug?: string) {
  return http.get<MembershipWithUser[]>(`/enterprise-spaces/${spaceId}/members`, {
    headers: spaceHeaders(spaceSlug),
  })
}

export async function addSpaceMember(
  spaceId: number,
  userId: number,
  role: MembershipRole = 'member',
  spaceSlug?: string,
) {
  return http.post(`/enterprise-spaces/${spaceId}/members`, null, {
    params: { user_id: userId, role },
    headers: spaceHeaders(spaceSlug),
  })
}

export async function updateSpaceMember(
  spaceId: number,
  userId: number,
  role: MembershipRole,
  spaceSlug?: string,
) {
  return http.patch(`/enterprise-spaces/${spaceId}/members/${userId}`, { role }, {
    headers: spaceHeaders(spaceSlug),
  })
}

export async function removeSpaceMember(spaceId: number, userId: number, spaceSlug?: string) {
  return http.delete(`/enterprise-spaces/${spaceId}/members/${userId}`, {
    headers: spaceHeaders(spaceSlug),
  })
}

export async function getSpaceMemberCount(spaceId: number) {
  return http.get<{ count: number }>(`/enterprise-spaces/${spaceId}/member-count`)
}

import client from './client'
import type { Organisation } from '../types'

export interface CreateOrgPayload {
  name: string
  industry: string
  country_code: string
  base_currency: string
  timezone: string
}

export const createOrg = (payload: CreateOrgPayload) =>
  client.post<Organisation>('/orgs/', payload)

export const listOrgs = () =>
  client.get<Organisation[]>('/orgs/')

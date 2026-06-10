import client from './client'
import type { MaturityProfile } from '../types'

export const getMaturity = (orgId: string) =>
  client.get<MaturityProfile>(`/forecast/orgs/${orgId}/maturity/`)

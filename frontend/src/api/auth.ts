import client from './client'
import type { User } from '../types'

export const register = (email: string, password: string, password_confirm: string, full_name: string) =>
  client.post('/auth/register/', { email, password, password_confirm, full_name })

export const login = (email: string, password: string) =>
  client.post<User>('/auth/login/', { email, password })

export const logout = () => client.post('/auth/logout/')

export const getMe = () => client.get<User>('/auth/me/')

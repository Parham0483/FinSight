import axios, { AxiosError } from 'axios'

const client = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,   // send HttpOnly cookies automatically
  headers: { 'Content-Type': 'application/json' },
})

let refreshing = false
let queue: Array<() => void> = []

client.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as typeof error.config & { _retry?: boolean }
    if (error.response?.status === 401 && !original._retry) {
      if (refreshing) {
        return new Promise((resolve) => {
          queue.push(() => resolve(client(original)))
        })
      }
      original._retry = true
      refreshing = true
      try {
        await axios.post('/api/v1/auth/refresh/', {}, { withCredentials: true })
        queue.forEach((cb) => cb())
        queue = []
        return client(original)
      } catch (refreshError) {
        queue = []
        return Promise.reject(refreshError)
      } finally {
        refreshing = false
      }
    }
    return Promise.reject(error)
  },
)

export default client

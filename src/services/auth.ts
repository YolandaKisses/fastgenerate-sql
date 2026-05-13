export type CurrentUser = {
  user_id: string
  name: string
  account: string
  role: string
}

type LoginResponse = {
  token: string
  token_type: string
  expires_in: number
  user: CurrentUser
}

const TOKEN_KEY = 'fg_sql_token'
const USER_KEY = 'fg_sql_user'
const LAST_DATASOURCE_KEY = 'fastgenerate_last_datasource_id'
const AUTH_API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

const buildUrl = (path: string) => {
  if (/^https?:\/\//.test(path)) return path
  return `${AUTH_API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export function setAuthSession(token: string, user: CurrentUser) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getCurrentUser(): CurrentUser | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as CurrentUser
  } catch {
    return null
  }
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(LAST_DATASOURCE_KEY)
}

export function isAuthenticated() {
  return Boolean(getAuthToken())
}

function pemToArrayBuffer(pem: string) {
  const base64 = pem
    .replace(/-----BEGIN PUBLIC KEY-----/g, '')
    .replace(/-----END PUBLIC KEY-----/g, '')
    .replace(/\s/g, '')
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes.buffer
}

function arrayBufferToBase64(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i += 1) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

export async function fetchPublicKey() {
  const res = await fetch(buildUrl('/auth/public-key'))
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data?.detail || '获取登录公钥失败')
  }
  return data.public_key as string
}

export async function encryptPassword(password: string, publicKeyPem: string) {
  const key = await crypto.subtle.importKey(
    'spki',
    pemToArrayBuffer(publicKeyPem),
    { name: 'RSA-OAEP', hash: 'SHA-256' },
    false,
    ['encrypt'],
  )
  const encrypted = await crypto.subtle.encrypt(
    { name: 'RSA-OAEP' },
    key,
    new TextEncoder().encode(password),
  )
  return arrayBufferToBase64(encrypted)
}

export async function login(account: string, password: string): Promise<LoginResponse> {
  const publicKey = await fetchPublicKey()
  const encryptedPassword = await encryptPassword(password, publicKey)
  const res = await fetch(buildUrl('/auth/login'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account, password: encryptedPassword }),
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data?.detail || data?.message || '登录失败')
  }
  setAuthSession(data.token, data.user)
  return data as LoginResponse
}

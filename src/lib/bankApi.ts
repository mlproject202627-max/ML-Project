import { apiFetch } from './api'

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export interface BankProfile {
  id: string
  name: string
  email: string
  role: string
  employee_code?: string | null
  job_title?: string | null
  department?: string | null
  branch_code?: string | null
  branch_name?: string | null
  mfa_enabled: boolean
  last_login?: string | null
  permissions: string[]
}

export interface BranchInfo {
  code: string
  name: string
  ifsc: string
  address?: string | null
  city?: string | null
  state?: string | null
  phone?: string | null
  manager_name?: string | null
}

export interface BankAccount {
  id: string
  account_number_masked: string
  account_type: string
  scheme?: string | null
  balance: number
  currency: string
  status: string
  opened_at: string
  last_txn_at?: string | null
  customer_id?: string
  customer_name?: string
}

export interface BankCustomer {
  id: string
  customer_id: string
  name: string
  email?: string | null
  phone?: string | null
  pan_masked?: string | null
  aadhaar_masked?: string | null
  segment?: string | null
  risk_rating?: string | null
  kyc_status?: string | null
  kyc_expiry?: string | null
  city?: string | null
  home_branch_code?: string | null
  relationship_manager?: string | null
  created_at: string
  address?: string | null
  dob?: string | null
  accounts: BankAccount[]
}

export interface BankTransaction {
  id: string
  txn_id: string
  account_id: string
  account_number_masked?: string | null
  posted_at: string
  direction: 'DR' | 'CR' | string
  amount: number
  currency: string
  channel: string
  category?: string | null
  narration?: string | null
  counterparty?: string | null
  counterparty_account_masked?: string | null
  balance_after?: number | null
  status: string
}

export interface BankLoan {
  id: string
  loan_id: string
  customer_id: string
  customer_name?: string | null
  product: string
  amount: number
  tenure_months: number
  interest_rate?: number | null
  emi?: number | null
  purpose?: string | null
  status: string
  stage?: string | null
  branch_code?: string | null
  created_at: string
  decided_at?: string | null
  remarks?: string | null
}

export interface BankKycCase {
  id: string
  case_number: string
  customer_id: string
  customer_name?: string | null
  case_type: string
  status: string
  priority: string
  documents_pending: string[]
  risk_rating?: string | null
  due_at?: string | null
  notes?: string | null
  created_at: string
}

export interface BankDocument {
  id: string
  doc_id: string
  customer_id?: string | null
  customer_name?: string | null
  title: string
  doc_type?: string | null
  file_name: string
  file_size?: number | null
  mime?: string | null
  version: number
  status: string
  created_at: string
}

export interface BankTicket {
  id: string
  ticket_number: string
  category: string
  subject: string
  description?: string | null
  priority: string
  status: string
  assignee_name?: string | null
  resolution?: string | null
  created_at: string
  updated_at: string
}

export interface PortalNotification {
  id: string
  category: string
  title: string
  body?: string | null
  link?: string | null
  read: boolean
  created_at: string
}

export interface Paged<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface TransferResult {
  txn_id: string
  status: string
  amount: number
  from_account_masked: string
  to_account_masked: string
  balance_after: number
  channel: string
  reference: string
  posted_at: string
}

export interface StatementData {
  account: BankAccount
  customer_name?: string | null
  period_months: number
  generated_at: string
  summary: { total_debits: number; total_credits: number; txn_count: number }
  transactions: BankTransaction[]
}

/* ------------------------------------------------------------------ */
/* Endpoints                                                           */
/* ------------------------------------------------------------------ */

const BASE = '/api/v1/bank'

export function getBankProfile(): Promise<BankProfile> {
  return apiFetch(`${BASE}/profile`)
}

export function getBranches(): Promise<BranchInfo[]> {
  return apiFetch(`${BASE}/branches`)
}

export function searchCustomers(params?: {
  q?: string
  segment?: string
  kyc_status?: string
  page?: number
  page_size?: number
}): Promise<Paged<BankCustomer>> {
  const qs = new URLSearchParams()
  if (params?.q) qs.set('q', params.q)
  if (params?.segment) qs.set('segment', params.segment)
  if (params?.kyc_status) qs.set('kyc_status', params.kyc_status)
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiFetch(`${BASE}/customers${query ? `?${query}` : ''}`)
}

export function getCustomerDetail(id: string): Promise<BankCustomer> {
  return apiFetch(`${BASE}/customers/${id}`)
}

export function getAccountDetail(accountId: string): Promise<BankAccount> {
  return apiFetch(`${BASE}/accounts/${accountId}`)
}

export function getAccountTransactions(params: {
  accountId: string
  page?: number
  page_size?: number
  direction?: string
  channel?: string
  status?: string
}): Promise<Paged<BankTransaction>> {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  if (params.direction) qs.set('direction', params.direction)
  if (params.channel) qs.set('channel', params.channel)
  if (params.status) qs.set('status', params.status)
  return apiFetch(`${BASE}/accounts/${params.accountId}/transactions?${qs.toString()}`)
}

export function searchTransactions(params?: {
  q?: string
  channel?: string
  status?: string
  page?: number
  page_size?: number
}): Promise<Paged<BankTransaction>> {
  const qs = new URLSearchParams()
  if (params?.q) qs.set('q', params.q)
  if (params?.channel) qs.set('channel', params.channel)
  if (params?.status) qs.set('status', params.status)
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiFetch(`${BASE}/transactions${query ? `?${query}` : ''}`)
}

export function createTransfer(input: {
  from_account_id: string
  to_account_number: string
  amount: number
  channel?: string
  narration?: string
}): Promise<TransferResult> {
  return apiFetch(`${BASE}/transfers`, { method: 'POST', body: JSON.stringify(input) })
}

export function getLoans(params?: {
  status?: string
  q?: string
  page?: number
  page_size?: number
}): Promise<Paged<BankLoan>> {
  const qs = new URLSearchParams()
  if (params?.status) qs.set('status', params.status)
  if (params?.q) qs.set('q', params.q)
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiFetch(`${BASE}/loans${query ? `?${query}` : ''}`)
}

export function createLoan(input: {
  customer_id: string
  product: string
  amount: number
  tenure_months: number
  purpose?: string
}): Promise<BankLoan> {
  return apiFetch(`${BASE}/loans`, { method: 'POST', body: JSON.stringify(input) })
}

export function updateLoan(
  loanId: string,
  patch: { status?: string; stage?: string; remarks?: string },
): Promise<BankLoan> {
  return apiFetch(`${BASE}/loans/${loanId}`, { method: 'PATCH', body: JSON.stringify(patch) })
}

export function getKycCases(params?: {
  status?: string
  priority?: string
  page?: number
  page_size?: number
}): Promise<Paged<BankKycCase>> {
  const qs = new URLSearchParams()
  if (params?.status) qs.set('status', params.status)
  if (params?.priority) qs.set('priority', params.priority)
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiFetch(`${BASE}/kyc${query ? `?${query}` : ''}`)
}

export function updateKycCase(
  caseNumber: string,
  patch: { status?: string; notes?: string },
): Promise<BankKycCase> {
  return apiFetch(`${BASE}/kyc/${caseNumber}`, { method: 'PATCH', body: JSON.stringify(patch) })
}

export function getStatement(accountId: string, months = 6): Promise<StatementData> {
  return apiFetch(`${BASE}/accounts/${accountId}/statement?months=${months}`)
}

export function getDocuments(params?: {
  q?: string
  doc_type?: string
  customer_id?: string
  page?: number
  page_size?: number
}): Promise<Paged<BankDocument>> {
  const qs = new URLSearchParams()
  if (params?.q) qs.set('q', params.q)
  if (params?.doc_type) qs.set('doc_type', params.doc_type)
  if (params?.customer_id) qs.set('customer_id', params.customer_id)
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiFetch(`${BASE}/documents${query ? `?${query}` : ''}`)
}

export function createDocument(input: {
  customer_id?: string
  title: string
  doc_type: string
  file_name: string
  file_size?: number
  mime?: string
}): Promise<BankDocument> {
  return apiFetch(`${BASE}/documents`, { method: 'POST', body: JSON.stringify(input) })
}

export function getPortalNotifications(): Promise<{ items: PortalNotification[]; unread: number }> {
  return apiFetch(`${BASE}/notifications`)
}

export function markPortalNotificationRead(id: string): Promise<{ ok: boolean }> {
  return apiFetch(`${BASE}/notifications/${id}/read`, { method: 'PATCH' })
}

export function markAllPortalNotificationsRead(): Promise<{ ok: boolean }> {
  return apiFetch(`${BASE}/notifications/read-all`, { method: 'PATCH' })
}

export function getTickets(params?: {
  status?: string
  page?: number
  page_size?: number
}): Promise<Paged<BankTicket>> {
  const qs = new URLSearchParams()
  if (params?.status) qs.set('status', params.status)
  if (params?.page) qs.set('page', String(params.page))
  if (params?.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiFetch(`${BASE}/support/tickets${query ? `?${query}` : ''}`)
}

export function createTicket(input: {
  category: string
  subject: string
  description?: string
  priority?: string
}): Promise<BankTicket> {
  return apiFetch(`${BASE}/support/tickets`, { method: 'POST', body: JSON.stringify(input) })
}

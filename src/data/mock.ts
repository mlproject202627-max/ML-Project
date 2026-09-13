import type {
  ActivityEvent,
  Alert,
  AnomalyKind,
  BehaviourVector,
  DetectorHealth,
  Employee,
  HeatCell,
  KindMeta,
  Severity,
  TrendPoint,
} from './types'

/* ------------------------------------------------------------------
   Deterministic pseudo-randomness so the demo data is rich but stable
   across reloads (no flicker, no hydration-style mismatch).
------------------------------------------------------------------ */
function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const clamp = (n: number, lo = 0, hi = 100) => Math.min(hi, Math.max(lo, n))
const r1 = (n: number) => Math.round(n * 10) / 10

/** Fixed "now" so relative timestamps never drift. */
export const NOW = new Date('2026-09-12T09:58:00Z')

/* ------------------------------------------------------------------
   Taxonomy
------------------------------------------------------------------ */
export const KIND_META: Record<AnomalyKind, KindMeta> = {
  off_hours_access: {
    label: 'Off-Hours Access',
    short: 'Off-Hours',
    color: '#a78bfa',
    description:
      'Resource access inside the 22:00–06:00 local window, weighted by the distance from the personal login-time baseline.',
  },
  lateral_movement: {
    label: 'Lateral Movement',
    short: 'Lateral',
    color: '#fb5a76',
    description:
      'Sequential authentication hops across hosts or subnets beyond the entitlements implied by the role.',
  },
  peer_deviation: {
    label: 'Peer-Group Deviation',
    short: 'Peer Drift',
    color: '#fba55a',
    description:
      'Behaviour diverging from the k-nearest peer centroid across volume, breadth and cadence features.',
  },
  privilege_escalation: {
    label: 'Privilege Escalation',
    short: 'PrivEsc',
    color: '#fbd05a',
    description:
      'Acquisition or exercise of elevated entitlements outside an approved change window or ticket.',
  },
  impossible_travel: {
    label: 'Impossible Travel',
    short: 'Geo Velocity',
    color: '#22d3ee',
    description:
      'Consecutive successful logins whose implied travel speed exceeds physical plausibility.',
  },
  dormant_revival: {
    label: 'Dormant Account Revival',
    short: 'Dormancy',
    color: '#34d399',
    description:
      'An identity silent for more than 45 days resuming activity with unusually high first-session volume.',
  },
  resource_sweeping: {
    label: 'Resource Sweeping',
    short: 'Sweeping',
    color: '#5ad0fb',
    description:
      'Rapid enumeration of many distinct shares, mailboxes or records far outside normal discovery patterns.',
  },
  session_anomaly: {
    label: 'Session Anomaly',
    short: 'Session',
    color: '#b8ad99',
    description:
      'Token replay, fingerprint mismatch or concurrent-session concurrency inconsistent with the device profile.',
  },
}

export const SEVERITY_META: Record<
  Severity,
  { label: string; hex: string; color: string; bg: string; ring: string }
> = {
  critical: {
    label: 'Critical',
    hex: '#fda4af',
    color: 'text-[#fda4af]',
    bg: 'bg-[#fda4af]/12',
    ring: 'ring-[#fda4af]/30',
  },
  high: {
    label: 'High',
    hex: '#fde68a',
    color: 'text-[#fde68a]',
    bg: 'bg-[#fde68a]/12',
    ring: 'ring-[#fde68a]/30',
  },
  medium: {
    label: 'Medium',
    hex: '#a7f3d0',
    color: 'text-[#a7f3d0]',
    bg: 'bg-[#a7f3d0]/10',
    ring: 'ring-[#a7f3d0]/25',
  },
  low: {
    label: 'Low',
    hex: '#69717a',
    color: 'text-[#69717a]',
    bg: 'bg-white/[0.04]',
    ring: 'ring-white/10',
  },
}

export const BEHAVIOUR_AXES = [
  { key: 'accessVolume', label: 'Access Volume' },
  { key: 'offHours', label: 'Off-Hours' },
  { key: 'resourceBreadth', label: 'Resource Breadth' },
  { key: 'privilegeUse', label: 'Privilege Use' },
  { key: 'peerDeviation', label: 'Peer Deviation' },
  { key: 'geoVelocity', label: 'Geo Velocity' },
] as const

/* ------------------------------------------------------------------
   Roster seeds — [accessVolume, offHours, resourceBreadth,
   privilegeUse, peerDeviation, geoVelocity]
------------------------------------------------------------------ */
interface RosterSeed {
  id: string
  name: string
  title: string
  department: Employee['department']
  peerGroup: string
  risk: number
  drift: number
  tenure: number
  location: string
  status: Employee['status']
  b: [number, number, number, number, number, number]
}

const ROSTER: RosterSeed[] = [
  {
    id: 'U-2291',
    name: 'Omar Haddad',
    title: 'Systems Administrator',
    department: 'IT Ops',
    peerGroup: 'IT-OPS-L3',
    risk: 94,
    drift: 4.6,
    tenure: 38,
    location: 'London, UK',
    status: 'watchlist',
    b: [78, 71, 96, 99, 92, 61],
  },
  {
    id: 'U-1043',
    name: 'Derek Hollis',
    title: 'Contract Data Analyst',
    department: 'Contract',
    peerGroup: 'EXT-CONTRACT',
    risk: 89,
    drift: 4.1,
    tenure: 4,
    location: 'Austin, US',
    status: 'watchlist',
    b: [95, 46, 84, 38, 90, 24],
  },
  {
    id: 'U-0871',
    name: 'Elena Petrova',
    title: 'Account Executive',
    department: 'Sales',
    peerGroup: 'SALES-AE',
    risk: 86,
    drift: 3.8,
    tenure: 21,
    location: 'London, UK',
    status: 'watchlist',
    b: [72, 33, 58, 19, 66, 98],
  },
  {
    id: 'U-0772',
    name: 'Priya Raghavan',
    title: 'Senior Financial Analyst',
    department: 'Finance',
    peerGroup: 'FIN-ANALYST',
    risk: 83,
    drift: 3.5,
    tenure: 52,
    location: 'Bengaluru, IN',
    status: 'watchlist',
    b: [81, 88, 62, 27, 79, 31],
  },
  {
    id: 'U-1904',
    name: 'Rajesh Kumar',
    title: 'DevOps Engineer',
    department: 'IT Ops',
    peerGroup: 'IT-OPS-L3',
    risk: 79,
    drift: 3.1,
    tenure: 44,
    location: 'Bengaluru, IN',
    status: 'watchlist',
    b: [68, 52, 74, 86, 71, 18],
  },
  {
    id: 'U-1508',
    name: 'Fatima Al-Sayed',
    title: 'Senior Recruiter',
    department: 'HR',
    peerGroup: 'HR-PEOPLE',
    risk: 74,
    drift: 2.9,
    tenure: 29,
    location: 'Dubai, AE',
    status: 'watchlist',
    b: [63, 91, 49, 22, 74, 12],
  },
  {
    id: 'U-0248',
    name: 'Carlos Mendes',
    title: 'Site Reliability Engineer',
    department: 'Engineering',
    peerGroup: 'ENG-PLATFORM',
    risk: 71,
    drift: 2.6,
    tenure: 33,
    location: 'Lisbon, PT',
    status: 'monitored',
    b: [58, 61, 77, 64, 63, 22],
  },
  {
    id: 'U-1147',
    name: 'Aisha Bello',
    title: 'Compliance Counsel',
    department: 'Legal',
    peerGroup: 'LEGAL-COUNSEL',
    risk: 66,
    drift: 2.4,
    tenure: 61,
    location: 'Lagos, NG',
    status: 'monitored',
    b: [54, 79, 52, 34, 68, 27],
  },
  {
    id: 'U-1622',
    name: 'Mei Lin Tan',
    title: 'AP Specialist',
    department: 'Finance',
    peerGroup: 'FIN-ANALYST',
    risk: 61,
    drift: 2.1,
    tenure: 17,
    location: 'Singapore, SG',
    status: 'monitored',
    b: [77, 41, 81, 15, 57, 14],
  },
  {
    id: 'U-1315',
    name: 'Nabil Farouk',
    title: 'Sales Director',
    department: 'Sales',
    peerGroup: 'SALES-LEAD',
    risk: 58,
    drift: 1.9,
    tenure: 47,
    location: 'Cairo, EG',
    status: 'monitored',
    b: [84, 29, 61, 31, 49, 22],
  },
  {
    id: 'U-2001',
    name: 'Viktor Sørensen',
    title: 'Security Engineer',
    department: 'IT Ops',
    peerGroup: 'IT-OPS-L3',
    risk: 54,
    drift: 1.7,
    tenure: 26,
    location: 'Copenhagen, DK',
    status: 'monitored',
    b: [49, 44, 58, 72, 52, 38],
  },
  {
    id: 'U-0440',
    name: 'Marcus Whitfield',
    title: 'Staff Engineer',
    department: 'Engineering',
    peerGroup: 'ENG-PLATFORM',
    risk: 51,
    drift: 1.6,
    tenure: 74,
    location: 'Manchester, UK',
    status: 'monitored',
    b: [71, 24, 55, 47, 61, 9],
  },
  {
    id: 'U-1733',
    name: 'Sofia Marchetti',
    title: 'Financial Controller',
    department: 'Finance',
    peerGroup: 'FIN-LEAD',
    risk: 43,
    drift: 1.2,
    tenure: 88,
    location: 'Milan, IT',
    status: 'monitored',
    b: [46, 21, 44, 58, 42, 13],
  },
  {
    id: 'U-0517',
    name: 'Grace Chen',
    title: 'Product Manager',
    department: 'Product',
    peerGroup: 'PROD-PM',
    risk: 38,
    drift: 0.9,
    tenure: 31,
    location: 'Vancouver, CA',
    status: 'cleared',
    b: [41, 26, 47, 18, 35, 11],
  },
  {
    id: 'U-0956',
    name: 'Liam O’Sullivan',
    title: 'Engineering Manager',
    department: 'Engineering',
    peerGroup: 'ENG-LEAD',
    risk: 33,
    drift: 0.7,
    tenure: 56,
    location: 'Dublin, IE',
    status: 'cleared',
    b: [37, 19, 39, 43, 28, 8],
  },
  {
    id: 'U-0863',
    name: 'Hannah Berg',
    title: 'Support Lead',
    department: 'Support',
    peerGroup: 'SUPPORT-LEAD',
    risk: 29,
    drift: 0.6,
    tenure: 41,
    location: 'Stockholm, SE',
    status: 'cleared',
    b: [44, 17, 35, 12, 24, 7],
  },
  {
    id: 'U-0178',
    name: 'Thomas Nguyen',
    title: 'Backend Engineer',
    department: 'Engineering',
    peerGroup: 'ENG-PLATFORM',
    risk: 24,
    drift: 0.4,
    tenure: 19,
    location: 'Sydney, AU',
    status: 'cleared',
    b: [31, 22, 33, 26, 19, 6],
  },
  {
    id: 'U-1855',
    name: 'Imani Okafor',
    title: 'Paralegal',
    department: 'Legal',
    peerGroup: 'LEGAL-COUNSEL',
    risk: 21,
    drift: 0.3,
    tenure: 14,
    location: 'Toronto, CA',
    status: 'cleared',
    b: [27, 15, 29, 9, 17, 5],
  },
  {
    id: 'U-0602',
    name: 'Dana Kowalski',
    title: 'People Partner',
    department: 'HR',
    peerGroup: 'HR-PEOPLE',
    risk: 17,
    drift: 0.2,
    tenure: 36,
    location: 'Warsaw, PL',
    status: 'cleared',
    b: [23, 13, 26, 11, 14, 4],
  },
  {
    id: 'U-2100',
    name: 'Jonas Weber',
    title: 'VP Operations',
    department: 'Executive',
    peerGroup: 'EXEC',
    risk: 26,
    drift: 0.5,
    tenure: 102,
    location: 'Zurich, CH',
    status: 'cleared',
    b: [35, 28, 52, 66, 21, 17],
  },
]

function makeHourly(seed: number, offHours: number): number[] {
  const rand = mulberry32(seed)
  return Array.from({ length: 24 }, (_, h) => {
    const business = Math.exp(-Math.pow(h - 13.5, 2) / 24)
    const night = Math.exp(-Math.pow(h - 3.5, 2) / 13)
    const base =
      business * (1 - offHours / 160) + night * (offHours / 90) + rand() * 0.18
    return clamp(Math.round(base * 82 + rand() * 18))
  })
}

const BASELINE_POOL: Employee['baselineShift'] = [
  {
    label: 'Median login time',
    baseline: '09:12 local',
    current: '03:41 local',
    delta: '+5h 29m',
  },
  {
    label: 'Files touched / week',
    baseline: '310',
    current: '2,480',
    delta: '+700%',
  },
  {
    label: 'Distinct shares mounted',
    baseline: '14',
    current: '63',
    delta: '+350%',
  },
  {
    label: 'Admin command usage',
    baseline: '2 / week',
    current: '41 / week',
    delta: '+1,950%',
  },
  {
    label: 'Peer-group z-score',
    baseline: '0.4σ',
    current: '3.9σ',
    delta: '+3.5σ',
  },
  {
    label: 'Dormant period',
    baseline: '0 days',
    current: '97 days',
    delta: 'revived',
  },
  {
    label: 'Seen from geolocation',
    baseline: 'London, UK',
    current: 'Singapore, SG',
    delta: '9,600 km',
  },
  {
    label: 'Mean session length',
    baseline: '42 min',
    current: '11 min',
    delta: '−74%',
  },
]

function makeBaseline(seed: number, b: RosterSeed['b']) {
  const ranked = b
    .map((value, i) => ({ value, i }))
    .sort((x, y) => y.value - x.value)
    .slice(0, 4)
  const poolByAxis: number[][] = [
    [1, 4, 7],
    [0, 6, 4],
    [1, 5, 4],
    [3, 5, 4],
    [4, 0, 2],
    [6, 2, 1],
  ]
  const rand = mulberry32(seed * 7 + 13)
  const seen = new Set<number>()
  const rows: Employee['baselineShift'] = []
  for (const { i } of ranked) {
    for (const idx of poolByAxis[i]) {
      if (seen.has(idx)) continue
      seen.add(idx)
      rows.push(BASELINE_POOL[idx])
      break
    }
    if (rows.length >= 4) break
  }
  while (rows.length < 3) {
    const idx = Math.floor(rand() * BASELINE_POOL.length)
    if (!seen.has(idx)) {
      seen.add(idx)
      rows.push(BASELINE_POOL[idx])
    }
  }
  return rows
}

export const employees: Employee[] = ROSTER.map((r, idx) => ({
  id: r.id,
  name: r.name,
  initials: r.name
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join(''),
  title: r.title,
  department: r.department,
  peerGroup: r.peerGroup,
  riskScore: r.risk,
  drift: r.drift,
  behaviour: {
    accessVolume: r.b[0],
    offHours: r.b[1],
    resourceBreadth: r.b[2],
    privilegeUse: r.b[3],
    peerDeviation: r.b[4],
    geoVelocity: r.b[5],
  },
  hourly: makeHourly(idx * 977 + 41, r.b[1]),
  lastSeen: [
    '3 min ago',
    '11 min ago',
    '24 min ago',
    '38 min ago',
    '52 min ago',
    '1 h ago',
    '2 h ago',
    '4 h ago',
    '6 h ago',
    '9 h ago',
  ][idx % 10],
  location: r.location,
  tenureMonths: r.tenure,
  openAlerts: 0,
  status: r.status,
  baselineShift: makeBaseline(idx + 1, r.b),
}))

const byId = new Map(employees.map((e) => [e.id, e]))

/* ------------------------------------------------------------------
   Alerts
------------------------------------------------------------------ */
type AlertSeed = Omit<Alert, 'employeeId'> & { employeeId: string }

const ALERT_SEEDS: AlertSeed[] = [
  {
    id: 'ALT-4821',
    employeeId: 'U-2291',
    kind: 'lateral_movement',
    severity: 'critical',
    confidence: 0.97,
    riskScore: 96,
    detectedAt: '2026-09-12T09:41:12Z',
    status: 'investigating',
    headline: 'Admin hop across 9 unmanaged subnets',
    narrative:
      'Service account followed by interactive SMB sessions into nine hosts that this identity has never authenticated against. Sequence matches a credential-reuse sweep rather than scheduled maintenance — no change ticket is linked to the window.',
    tactic: 'TA0008 · Lateral Movement',
    asset: 'corp-fs-04, dc-edge-02, +7 hosts',
    sourceIp: '10.42.9.117',
    geo: 'London, UK',
    detector: 'Graph Lateral Movement v4',
    factors: [
      { label: 'Newly contacted hosts (24h)', weight: 0.34, detail: '9 hosts, 0 prior history' },
      { label: 'Privileged session count', weight: 0.27, detail: '14 admin shells in 22 min' },
      { label: 'Peer-group rarity', weight: 0.21, detail: '0 of 41 IT-OPS-L3 peers' },
      { label: 'Change-window mismatch', weight: 0.18, detail: 'No linked CHG ticket' },
    ],
  },
  {
    id: 'ALT-4817',
    employeeId: 'U-0772',
    kind: 'off_hours_access',
    severity: 'high',
    confidence: 0.93,
    riskScore: 88,
    detectedAt: '2026-09-12T09:12:44Z',
    status: 'new',
    headline: 'AP ledger and vendor master read at 03:41',
    narrative:
      'Analyst with no payment-write entitlement opened the accounts-payable ledger and full vendor master outside her shift, then exported a CSV to a personal cloud-sync folder.',
    tactic: 'TA0009 · Collection',
    asset: 'fin-ap-ledger, vendor-master',
    sourceIp: '172.20.4.88',
    geo: 'Bengaluru, IN',
    detector: 'Behavioural Autoencoder',
    factors: [
      { label: 'Off-hours offset', weight: 0.31, detail: '03:41 vs 09:12 baseline' },
      { label: 'Entitlement mismatch', weight: 0.26, detail: 'read on restricted vendor master' },
      { label: 'Export to unmanaged path', weight: 0.24, detail: '~/Dropbox/AP_0926.csv' },
      { label: 'Peer-group rarity', weight: 0.19, detail: '1 of 34 FIN-ANALYST peers' },
    ],
  },
  {
    id: 'ALT-4812',
    employeeId: 'U-1043',
    kind: 'dormant_revival',
    severity: 'high',
    confidence: 0.9,
    riskScore: 85,
    detectedAt: '2026-09-12T08:47:03Z',
    status: 'new',
    headline: 'Contractor account revived after 97 days idle',
    narrative:
      'Identity was silent since 07 June while its contract lapsed. First session back pulled 41,000 CRM rows in 9 minutes — roughly 26× the contract role’s weekly median.',
    tactic: 'TA0010 · Exfiltration',
    asset: 'crm-prod/opportunities',
    sourceIp: '73.114.202.19',
    geo: 'Austin, US',
    detector: 'Isolation Forest Ensemble',
    factors: [
      { label: 'Dormancy length', weight: 0.33, detail: '97 days since last auth' },
      { label: 'First-session volume', weight: 0.29, detail: '41,000 rows vs 1,580 median' },
      { label: 'Contract status', weight: 0.22, detail: 'lapsed 30 Jun 2026' },
      { label: 'Bulk query shape', weight: 0.16, detail: 'unbounded SELECT, no filter' },
    ],
  },
  {
    id: 'ALT-4809',
    employeeId: 'U-2291',
    kind: 'privilege_escalation',
    severity: 'critical',
    confidence: 0.95,
    riskScore: 93,
    detectedAt: '2026-09-12T08:22:31Z',
    status: 'investigating',
    headline: 'SeBackupPrivilege acquired outside change window',
    narrative:
      'Administrator granted the backup privilege to a non-service principal, then used it to read the SAM hive from a domain controller during an unrelated maintenance slot.',
    tactic: 'TA0004 · Privilege Escalation',
    asset: 'dc-edge-02',
    sourceIp: '10.42.9.117',
    geo: 'London, UK',
    detector: 'Rule Sentinel',
    factors: [
      { label: 'Privilege grant anomaly', weight: 0.36, detail: 'SeBackupPrivilege on DC' },
      { label: 'Change-window mismatch', weight: 0.28, detail: '04:22, window closed 04:00' },
      { label: 'Hive read target', weight: 0.22, detail: 'SAM + SECURITY hives' },
      { label: 'Peer-group rarity', weight: 0.14, detail: '0 of 41 peers, 180d' },
    ],
  },
  {
    id: 'ALT-4803',
    employeeId: 'U-0871',
    kind: 'impossible_travel',
    severity: 'critical',
    confidence: 0.91,
    riskScore: 90,
    detectedAt: '2026-09-12T07:55:18Z',
    status: 'new',
    headline: 'London → Singapore in 38 minutes',
    narrative:
      'Two successful MFA-authenticated sessions from geolocations 10,850 km apart, implying 17,100 km/h of travel. Both sessions were concurrent for six minutes.',
    tactic: 'TA0001 · Initial Access',
    asset: 'sso-gateway, salesforce',
    sourceIp: '103.6.14.220',
    geo: 'Singapore, SG',
    detector: 'Access Sequence Transformer',
    factors: [
      { label: 'Implied travel speed', weight: 0.38, detail: '17,100 km/h' },
      { label: 'Session concurrency', weight: 0.27, detail: '6 min overlap' },
      { label: 'ASN reputation', weight: 0.2, detail: 'residential proxy, first seen' },
      { label: 'Device fingerprint', weight: 0.15, detail: 'new macOS build' },
    ],
  },
  {
    id: 'ALT-4798',
    employeeId: 'U-1904',
    kind: 'resource_sweeping',
    severity: 'high',
    confidence: 0.86,
    riskScore: 79,
    detectedAt: '2026-09-12T07:31:52Z',
    status: 'investigating',
    headline: 'Enumerated 63 finance shares in 12 minutes',
    narrative:
      'DevOps engineer with no finance entitlement walked the share tree from a build host, touching 63 mounted paths at a cadence no human review workflow would produce.',
    tactic: 'TA0007 · Discovery',
    asset: 'fin-* (63 shares)',
    sourceIp: '10.19.3.44',
    geo: 'Bengaluru, IN',
    detector: 'Peer-Group Clustering',
    factors: [
      { label: 'Distinct share breadth', weight: 0.35, detail: '63 vs 6 median' },
      { label: 'Traversal rate', weight: 0.26, detail: '5.2 shares / min' },
      { label: 'Source host trust', weight: 0.23, detail: 'unmanaged build host' },
      { label: 'Access denial ratio', weight: 0.16, detail: '38% denied' },
    ],
  },
  {
    id: 'ALT-4794',
    employeeId: 'U-1622',
    kind: 'peer_deviation',
    severity: 'medium',
    confidence: 0.78,
    riskScore: 64,
    detectedAt: '2026-09-12T06:58:09Z',
    status: 'new',
    headline: 'Vendor payment cadence 2.1σ off peer median',
    narrative:
      'Approval-to-payment latency collapsed from 4.2 days to under 9 hours across 22 invoices, all from three newly created vendors.',
    tactic: 'TA0006 · Credential Access',
    asset: 'vendor-master (3 new)',
    sourceIp: '172.20.7.31',
    geo: 'Singapore, SG',
    detector: 'Behavioural Autoencoder',
    factors: [
      { label: 'Cadence deviation', weight: 0.32, detail: '9 h vs 4.2 d median' },
      { label: 'New vendor concentration', weight: 0.28, detail: '3 vendors, 22 invoices' },
      { label: 'Maker-checker overlap', weight: 0.24, detail: 'self-approved 4 items' },
      { label: 'Peer-group z-score', weight: 0.16, detail: '2.1σ' },
    ],
  },
  {
    id: 'ALT-4789',
    employeeId: 'U-2001',
    kind: 'session_anomaly',
    severity: 'low',
    confidence: 0.71,
    riskScore: 44,
    detectedAt: '2026-09-12T06:14:37Z',
    status: 'dismissed',
    headline: 'Session token replayed from two ASNs',
    narrative:
      'Refresh token presented from a corporate VPN and a consumer ISP within 90 seconds. Likely a legitimate laptop-to-phone handoff; closed as benign.',
    tactic: 'TA0005 · Defense Evasion',
    asset: 'sso-gateway',
    sourceIp: '185.44.76.2',
    geo: 'Copenhagen, DK',
    detector: 'Rule Sentinel',
    factors: [
      { label: 'Token replay window', weight: 0.4, detail: '90 s across two ASNs' },
      { label: 'Known device set', weight: 0.34, detail: '2 of 3 devices trusted' },
      { label: 'Travel plausibility', weight: 0.26, detail: '14 km, plausible' },
    ],
  },
  {
    id: 'ALT-4785',
    employeeId: 'U-1147',
    kind: 'off_hours_access',
    severity: 'medium',
    confidence: 0.74,
    riskScore: 62,
    detectedAt: '2026-09-12T05:42:11Z',
    status: 'investigating',
    headline: 'Weekend case pulls from personal device',
    narrative:
      'Counsel opened eleven litigation case folders on a Saturday from a device fingerprint not in her managed fleet. Volume is 3.4σ above her own weekend baseline.',
    tactic: 'TA0009 · Collection',
    asset: 'legal-matters (11 folders)',
    sourceIp: '41.58.190.7',
    geo: 'Lagos, NG',
    detector: 'Isolation Forest Ensemble',
    factors: [
      { label: 'Unmanaged device', weight: 0.33, detail: 'fingerprint not in fleet' },
      { label: 'Weekend volume', weight: 0.29, detail: '3.4σ above own baseline' },
      { label: 'Matter sensitivity', weight: 0.23, detail: '3 sealed matters' },
      { label: 'Off-hours window', weight: 0.15, detail: 'Sat 14:10 local' },
    ],
  },
  {
    id: 'ALT-4780',
    employeeId: 'U-0248',
    kind: 'lateral_movement',
    severity: 'high',
    confidence: 0.84,
    riskScore: 76,
    detectedAt: '2026-09-12T04:29:58Z',
    status: 'new',
    headline: 'SSH pivot across 14 hosts with no ticket',
    narrative:
      'SRE identity chained SSH tunnels across fourteen production hosts using a rotated key that has not appeared in any prior session.',
    tactic: 'TA0008 · Lateral Movement',
    asset: 'prod-eu-* (14 hosts)',
    sourceIp: '10.66.1.9',
    geo: 'Lisbon, PT',
    detector: 'Graph Lateral Movement v4',
    factors: [
      { label: 'Host chain depth', weight: 0.31, detail: 'depth 14, longest 3' },
      { label: 'Novel key material', weight: 0.27, detail: 'key unseen in 180d' },
      { label: 'Missing change ticket', weight: 0.24, detail: 'no linked CHG' },
      { label: 'Bastion bypass', weight: 0.18, detail: 'direct to prod-eu-07' },
    ],
  },
  {
    id: 'ALT-4776',
    employeeId: 'U-1315',
    kind: 'resource_sweeping',
    severity: 'medium',
    confidence: 0.76,
    riskScore: 59,
    detectedAt: '2026-09-12T03:18:40Z',
    status: 'new',
    headline: 'Bulk export of 4,100 opportunity records',
    narrative:
      'Sales director exported the full pipeline rather than his own territory — 4,100 records spanning eleven regions, three days before a resignation window opens.',
    tactic: 'TA0010 · Exfiltration',
    asset: 'salesforce/opportunities',
    sourceIp: '196.44.12.8',
    geo: 'Cairo, EG',
    detector: 'Behavioural Autoencoder',
    factors: [
      { label: 'Export scope', weight: 0.34, detail: '11 regions vs 1 owned' },
      { label: 'Record volume', weight: 0.28, detail: '4,100 vs 240 median' },
      { label: 'Off-hours timing', weight: 0.22, detail: '05:18 local' },
      { label: 'HR signal', weight: 0.16, detail: 'resignation window open' },
    ],
  },
  {
    id: 'ALT-4765',
    employeeId: 'U-1508',
    kind: 'off_hours_access',
    severity: 'high',
    confidence: 0.88,
    riskScore: 81,
    detectedAt: '2026-09-12T02:33:24Z',
    status: 'new',
    headline: 'Compensation records viewed at 01:20',
    narrative:
      'Recruiter queried the compensation band table for 240 employees outside her assigned org, from a hotel network in a city she is not travelling to.',
    tactic: 'TA0009 · Collection',
    asset: 'hr-comp-bands',
    sourceIp: '94.203.55.18',
    geo: 'Dubai, AE',
    detector: 'Peer-Group Clustering',
    factors: [
      { label: 'Out-of-org scope', weight: 0.32, detail: '240 vs 18 assigned' },
      { label: 'Off-hours offset', weight: 0.27, detail: '01:20 vs 08:40 baseline' },
      { label: 'Untrusted network', weight: 0.24, detail: 'hotel captive portal' },
      { label: 'Repeat pattern', weight: 0.17, detail: '4th occurrence in 9 d' },
    ],
  },
  {
    id: 'ALT-4759',
    employeeId: 'U-0517',
    kind: 'dormant_revival',
    severity: 'low',
    confidence: 0.68,
    riskScore: 39,
    detectedAt: '2026-09-12T01:47:02Z',
    status: 'dismissed',
    headline: 'Legacy analytics token reactivated',
    narrative:
      'A long-unused personal API token made its first call in 61 days, reading a dashboard it owns. Consistent with a forgotten CI job; closed.',
    tactic: 'TA0003 · Persistence',
    asset: 'analytics-api',
    sourceIp: '10.8.22.5',
    geo: 'Vancouver, CA',
    detector: 'Rule Sentinel',
    factors: [
      { label: 'Token dormancy', weight: 0.42, detail: '61 days idle' },
      { label: 'Scope limited', weight: 0.33, detail: 'read-only, own dashboard' },
      { label: 'Source host', weight: 0.25, detail: 'known CI runner' },
    ],
  },
]

export const alerts: Alert[] = ALERT_SEEDS.map((a) => ({ ...a }))

for (const alert of alerts) {
  const emp = byId.get(alert.employeeId)
  if (emp) emp.openAlerts += 1
}

/* ------------------------------------------------------------------
   Trending
------------------------------------------------------------------ */
export const trend: TrendPoint[] = (() => {
  const rand = mulberry32(20260912)
  const labels = [
    'Aug 30', 'Aug 31', 'Sep 01', 'Sep 02', 'Sep 03', 'Sep 04', 'Sep 05',
    'Sep 06', 'Sep 07', 'Sep 08', 'Sep 09', 'Sep 10', 'Sep 11', 'Sep 12',
  ]
  return labels.map((label, i) => {
    const weekend = i % 7 === 2 || i % 7 === 3
    const base = weekend ? 9 : 21
    const surge = i > 9 ? (i - 9) * 7 : 0
    const anomalies = Math.round(base + surge + rand() * 8)
    const meanRisk = r1(24 + surge * 0.9 + rand() * 7)
    return { label, anomalies, meanRisk, baseline: r1(12 + rand() * 3) }
  })
})()

/* ------------------------------------------------------------------
   Activity heatmap (7 days × 24 hours)
------------------------------------------------------------------ */
export const heatmap: HeatCell[] = (() => {
  const rand = mulberry32(771)
  const cells: HeatCell[] = []
  for (let day = 0; day < 7; day++) {
    for (let hour = 0; hour < 24; hour++) {
      const business = Math.exp(-Math.pow(hour - 14, 2) / 30)
      const weekend = day >= 5
      const base = business * (weekend ? 26 : 88)
      const night = hour < 6 || hour > 22 ? 12 + rand() * 26 : 0
      cells.push({ day, hour, intensity: clamp(Math.round(base + night + rand() * 10)) })
    }
  }
  return cells
})()

/* ------------------------------------------------------------------
   Live activity stream
------------------------------------------------------------------ */
export const events: ActivityEvent[] = [
  { id: 'EV-99120', employeeId: 'U-2291', ts: '09:56:41', action: 'SMB session opened', target: 'dc-edge-02$', verdict: 'suspicious', risk: 92 },
  { id: 'EV-99117', employeeId: 'U-0772', ts: '09:54:02', action: 'Bulk read', target: 'vendor-master (4,210 rows)', verdict: 'suspicious', risk: 87 },
  { id: 'EV-99114', employeeId: 'U-0863', ts: '09:52:30', action: 'Ticket updated', target: 'SUP-4471', verdict: 'normal', risk: 8 },
  { id: 'EV-99109', employeeId: 'U-2291', ts: '09:50:18', action: 'Privilege token requested', target: 'SeBackupPrivilege', verdict: 'suspicious', risk: 95 },
  { id: 'EV-99101', employeeId: 'U-0178', ts: '09:48:55', action: 'Repo push', target: 'platform/ingest', verdict: 'normal', risk: 11 },
  { id: 'EV-99096', employeeId: 'U-1043', ts: '09:47:21', action: 'Table export', target: 'crm-prod/opportunities', verdict: 'suspicious', risk: 89 },
  { id: 'EV-99088', employeeId: 'U-1508', ts: '09:44:09', action: 'Record query', target: 'hr-comp-bands', verdict: 'notable', risk: 64 },
  { id: 'EV-99081', employeeId: 'U-0956', ts: '09:42:47', action: 'Code review', target: 'PR #2291', verdict: 'normal', risk: 6 },
  { id: 'EV-99077', employeeId: 'U-1904', ts: '09:40:12', action: 'Share mount', target: 'fin-ap-ledger', verdict: 'notable', risk: 58 },
  { id: 'EV-99070', employeeId: 'U-0871', ts: '09:38:58', action: 'MFA challenge', target: 'sso-gateway', verdict: 'notable', risk: 55 },
  { id: 'EV-99063', employeeId: 'U-0602', ts: '09:36:04', action: 'Onboarding doc read', target: 'hr-handbook-v9', verdict: 'normal', risk: 5 },
  { id: 'EV-99055', employeeId: 'U-0248', ts: '09:33:40', action: 'SSH session', target: 'prod-eu-07', verdict: 'suspicious', risk: 78 },
  { id: 'EV-99048', employeeId: 'U-1622', ts: '09:31:19', action: 'Invoice approved', target: 'INV-88213', verdict: 'notable', risk: 61 },
  { id: 'EV-99039', employeeId: 'U-2100', ts: '09:28:52', action: 'Board deck opened', target: 'exec-q3-strategy', verdict: 'normal', risk: 14 },
  { id: 'EV-99031', employeeId: 'U-1315', ts: '09:26:07', action: 'Report export', target: 'salesforce/pipeline-all', verdict: 'suspicious', risk: 74 },
  { id: 'EV-99024', employeeId: 'U-1855', ts: '09:23:33', action: 'Matter file read', target: 'legal-matters/2291', verdict: 'normal', risk: 9 },
  { id: 'EV-99016', employeeId: 'U-2291', ts: '09:20:44', action: 'Registry hive read', target: 'dc-edge-02/SAM', verdict: 'suspicious', risk: 97 },
  { id: 'EV-99008', employeeId: 'U-0440', ts: '09:18:02', action: 'Repo clone', target: 'platform/telemetry', verdict: 'normal', risk: 12 },
  { id: 'EV-99001', employeeId: 'U-1147', ts: '09:15:26', action: 'Case folder open', target: 'legal-matters/sealed-3', verdict: 'notable', risk: 63 },
  { id: 'EV-99993', employeeId: 'U-1733', ts: '09:12:49', action: 'Journal posted', target: 'GL-4400', verdict: 'normal', risk: 10 },
]

/* ------------------------------------------------------------------
   Detector fleet
------------------------------------------------------------------ */
export const detectors: DetectorHealth[] = [
  { name: 'Behavioural Autoencoder', family: 'Deep reconstruction', status: 'healthy', precision: 0.94, recall: 0.89, f1: 0.914, auc: 0.972, drift: 0.04, lastTrained: '6 h ago', features: 184, throughput: '12.4k events/s' },
  { name: 'Isolation Forest Ensemble', family: 'Tree ensemble', status: 'healthy', precision: 0.88, recall: 0.92, f1: 0.899, auc: 0.958, drift: 0.07, lastTrained: '6 h ago', features: 96, throughput: '48.1k events/s' },
  { name: 'Peer-Group Clustering', family: 'k-means · 64 clusters', status: 'healthy', precision: 0.81, recall: 0.77, f1: 0.789, auc: 0.921, drift: 0.11, lastTrained: '1 d ago', features: 64, throughput: '30.6k events/s' },
  { name: 'Access Sequence Transformer', family: 'Sequence model', status: 'degraded', precision: 0.79, recall: 0.85, f1: 0.818, auc: 0.944, drift: 0.23, lastTrained: '3 d ago', features: 512, throughput: '8.2k events/s' },
  { name: 'Graph Lateral Movement', family: 'Graph neural net', status: 'healthy', precision: 0.96, recall: 0.83, f1: 0.890, auc: 0.981, drift: 0.05, lastTrained: '12 h ago', features: 240, throughput: '5.7k events/s' },
  { name: 'Rule Sentinel', family: 'Deterministic policy', status: 'training', precision: 0.99, recall: 0.41, f1: 0.580, auc: 0.705, drift: 0.0, lastTrained: 'retraining', features: 412, throughput: '90.3k events/s' },
]

/* ------------------------------------------------------------------
   Derived aggregates used by the chrome
------------------------------------------------------------------ */
export const summary = {
  monitored: 12480,
  monitoredDelta: 3.2,
  activeAlerts: alerts.filter((a) => a.status !== 'dismissed' && a.status !== 'contained').length,
  criticalAlerts: alerts.filter((a) => a.severity === 'critical').length,
  meanRisk: r1(alerts.reduce((s, a) => s + a.riskScore, 0) / alerts.length),
  watchlist: employees.filter((e) => e.status === 'watchlist').length,
  blockedSessions: 37,
  eventsToday: 2_418_902,
  falsePositiveRate: 4.1,
  coverage: 98.4,
}

export function employeeById(id: string): Employee | undefined {
  return byId.get(id)
}

/**
 * Mean behaviour vector for an identity's peer group — the baseline the
 * anomaly models compare against. Falls back to the estate mean when an
 * identity is the only member of its group.
 */
export function peerBaseline(emp: Employee): BehaviourVector {
  const sameGroup = employees.filter(
    (e) => e.peerGroup === emp.peerGroup && e.id !== emp.id,
  )
  const pool = sameGroup.length > 0 ? sameGroup : employees.filter((e) => e.id !== emp.id)
  const axes: (keyof BehaviourVector)[] = [
    'accessVolume',
    'offHours',
    'resourceBreadth',
    'privilegeUse',
    'peerDeviation',
    'geoVelocity',
  ]
  const out = {} as BehaviourVector
  for (const axis of axes) {
    const sum = pool.reduce((s, e) => s + e.behaviour[axis], 0)
    out[axis] = Math.round(sum / pool.length)
  }
  return out
}

export function alertsForEmployee(id: string): Alert[] {
  return alerts.filter((a) => a.employeeId === id)
}

export const departmentBreakdown = (() => {
  const map = new Map<string, { count: number; risk: number }>()
  for (const e of employees) {
    const cur = map.get(e.department) ?? { count: 0, risk: 0 }
    cur.count += 1
    cur.risk += e.riskScore
    map.set(e.department, cur)
  }
  return [...map.entries()]
    .map(([department, v]) => ({
      department,
      count: v.count,
      meanRisk: r1(v.risk / v.count),
    }))
    .sort((a, b) => b.meanRisk - a.meanRisk)
})()

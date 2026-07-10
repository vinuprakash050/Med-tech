/**
 * dummyMedData.js
 * ──────────────────────────────────────────────────────────────────
 * Generates deterministic dummy expiry dates, a single discount offer,
 * and nearby shop data for any medicine alternative.
 *
 * Rules:
 *  • Minimum expiry is 60 days (2 months) — medicines expiring sooner
 *    are not listed at all. The generator always produces ≥ 60 days.
 *  • A single discount is shown, not multiple tiers.
 *    The message is contextual:
 *      60–90 days  → "Expiry within 3 months"  → 8–12% off
 *      91–180 days → "Expiry within 6 months"  → 4–7%  off
 *      > 180 days  → "Expiry within a year"    → 1–3%  off
 */

/* ── Seeded PRNG (mulberry32) ─────────────────────── */
function hashStr(str) {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
    h >>>= 0
  }
  return h
}

function mulberry32(seed) {
  let s = seed >>> 0
  return function () {
    s += 0x6d2b79f5
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function seededRng(key) {
  return mulberry32(hashStr(String(key)))
}

/* ── Helpers ──────────────────────────────────────── */
function ri(rng, min, max) {
  return Math.floor(rng() * (max - min + 1)) + min
}
function pick(rng, arr) {
  return arr[Math.floor(rng() * arr.length)]
}
function addDays(d, n) {
  const r = new Date(d); r.setDate(r.getDate() + n); return r
}
function fmtDate(d) {
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

/* ── Name pools ───────────────────────────────────── */
const SHOP_PREFIXES = [
  'Apollo', 'MedPlus', 'Frank Ross', 'Wellness Forever', 'Guardian',
  'Thyrocare', 'Sanjivini', 'HealthFirst', 'City Pharma', 'Aarogya',
  'Lifeline', 'Sunrise', 'Care & Cure', 'Green Cross', 'Janata',
]
const SHOP_SUFFIXES = [
  'Pharmacy', 'Medical Store', 'Chemist', 'Drug Store', 'Health Store',
]
const AREAS = [
  'Anna Nagar', 'T. Nagar', 'Velachery', 'Adyar', 'Guindy',
  'Nungambakkam', 'Mylapore', 'Tambaram', 'Perambur', 'Kodambakkam',
  'Salt Lake', 'Park Street', 'Bandra', 'Koramangala', 'Indiranagar',
  'Jayanagar', 'Malviya Nagar', 'Laxmi Nagar', 'Sector 18', 'MG Road',
]

const BASE_LAT = 13.0827
const BASE_LNG = 80.2707

/* ── Discount config by expiry bucket ────────────── */
//  Minimum allowed: 60 days.  Anything under is not listed.
const BUCKETS = [
  {
    minDays: 60,
    maxDays: 90,
    label:   'Expiry within 3 months',
    urgency: 'medium',       // amber
    discountMin: 8,
    discountMax: 12,
  },
  {
    minDays: 91,
    maxDays: 180,
    label:   'Expiry within 6 months',
    urgency: 'low',          // green
    discountMin: 4,
    discountMax: 7,
  },
  {
    minDays: 181,
    maxDays: 365,
    label:   'Expiry within a year',
    urgency: 'minimal',      // blue
    discountMin: 1,
    discountMax: 3,
  },
]

/* ── Main export ──────────────────────────────────── */
/**
 * generateMedDummyData(key)
 *
 * @param {string|number} key  medicine id or name
 * @returns {{
 *   expiryDate:      string,
 *   daysToExpiry:    number,
 *   expiryUrgency:   'medium'|'low'|'minimal',
 *   discount: {
 *     percent:  number,
 *     label:    string,   // "Expiry within 3 months"
 *     urgency:  string,
 *   },
 *   shops: Array<{ name, area, distance, lat, lng, rating, inStock }>,
 * }}
 */
export function generateMedDummyData(key) {
  const rng = seededRng(key)

  /* ── Expiry: always ≥ 60 days (2 months minimum) ── */
  // Weight: 35% in 60-90d window, 40% in 91-180d, 25% beyond 180d
  const roll = rng()
  let daysToExpiry
  if      (roll < 0.35) daysToExpiry = ri(rng, 60,  90)
  else if (roll < 0.75) daysToExpiry = ri(rng, 91,  180)
  else                  daysToExpiry = ri(rng, 181, 365)

  const today      = new Date()
  const expiryDate = addDays(today, daysToExpiry)

  /* ── Pick bucket ── */
  const bucket = BUCKETS.find(b => daysToExpiry >= b.minDays && daysToExpiry <= b.maxDays)
    ?? BUCKETS[BUCKETS.length - 1]   // fallback to last (shouldn't happen)

  const discountPct = ri(rng, bucket.discountMin, bucket.discountMax)

  const discount = {
    percent: discountPct,
    label:   bucket.label,
    urgency: bucket.urgency,
  }

  /* ── Nearby shops ── */
  const shopCount = ri(rng, 4, 6)
  const shops = []
  for (let i = 0; i < shopCount; i++) {
    const prefix  = pick(rng, SHOP_PREFIXES)
    const suffix  = pick(rng, SHOP_SUFFIXES)
    const area    = pick(rng, AREAS)
    const km      = parseFloat((rng() * 4.5 + 0.3).toFixed(1))
    const rating  = parseFloat((rng() * 1.5 + 3.5).toFixed(1))
    const latOff  = (rng() - 0.5) * 0.06
    const lngOff  = (rng() - 0.5) * 0.06
    const inStock = rng() > 0.2

    shops.push({
      name:     `${prefix} ${suffix}`,
      area,
      distance: km,
      lat:      parseFloat((BASE_LAT + latOff).toFixed(6)),
      lng:      parseFloat((BASE_LNG + lngOff).toFixed(6)),
      rating,
      inStock,
    })
  }
  shops.sort((a, b) => a.distance - b.distance)

  return {
    expiryDate,
    expiryDateStr:   fmtDate(expiryDate),
    daysToExpiry,
    expiryUrgency:   bucket.urgency,
    discount,
    shops,
  }
}

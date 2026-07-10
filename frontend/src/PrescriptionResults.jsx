import React, { useMemo, useState } from 'react'
import PrescriptionSummary from './PrescriptionSummary.jsx'
import PrescriptionSidebar from './PrescriptionSidebar.jsx'
import { generateMedDummyData } from './dummyMedData.js'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

/* ─── helpers (duplicated from App.jsx to keep component self-contained) ─── */

function fmt(price) {
  const n = parseFloat(price)
  return isNaN(n) ? null : n % 1 === 0 ? String(n) : n.toFixed(2)
}

function savePct(refPrice, altPrice) {
  const r = parseFloat(refPrice)
  const a = parseFloat(altPrice)
  if (!r || isNaN(r) || isNaN(a) || a >= r) return null
  return Math.round(((r - a) / r) * 100)
}

function friendlyError(err) {
  const raw = err instanceof Error ? err.message : String(err)
  try {
    const d = JSON.parse(raw)
    if (typeof d.detail === 'string') return d.detail
  } catch { /* fall through */ }
  return raw.replace(/^Error:\s*/, '')
}

/* ─── Small shared badge components ─────────────────────────────────────── */

function FdaBadge({ available }) {
  if (available === undefined || available === null) return null
  return (
    <span className={`badge ${available ? 'badge--success' : 'badge--soft'}`}>
      {available ? 'FDA Verified' : 'No FDA Data'}
    </span>
  )
}

function GenericBadge({ isGeneric }) {
  if (isGeneric === undefined || isGeneric === null) return null
  return (
    <span className={`badge ${isGeneric ? 'badge--generic' : 'badge--brand'}`}>
      {isGeneric ? 'Generic' : 'Brand'}
    </span>
  )
}

function CheckIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{marginRight:3,flexShrink:0}}>
      <circle cx="6" cy="6" r="5" fill="#dcfce7"/>
      <path d="M3.5 6l2 2 3-3" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

/* ─── Shops Map Modal ────────────────────────────── */

function ShopsMapModal({ shops, medicineName, onClose }) {
  React.useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  function mapsUrl(shop) {
    return `https://www.google.com/maps/dir/?api=1&destination=${shop.lat},${shop.lng}`
  }

  function starStr(rating) {
    const full  = Math.floor(rating)
    const half  = rating - full >= 0.5 ? 1 : 0
    const empty = 5 - full - half
    return '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(empty)
  }

  return (
    <div className="shops-overlay" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="shops-modal" role="dialog" aria-modal="true" aria-label="Nearby pharmacy shops">
        <div className="shops-modal__header">
          <div>
            <div className="shops-modal__eyebrow">Nearby pharmacies</div>
            <div className="shops-modal__title">{medicineName}</div>
          </div>
          <button className="shops-modal__close" onClick={onClose} aria-label="Close">
            <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <div className="shops-map-canvas" aria-hidden="true">
          {shops.map((shop, i) => {
            const lats   = shops.map(s => s.lat)
            const lngs   = shops.map(s => s.lng)
            const minLat = Math.min(...lats), maxLat = Math.max(...lats)
            const minLng = Math.min(...lngs), maxLng = Math.max(...lngs)
            const rangeX = maxLng - minLng || 0.001
            const rangeY = maxLat - minLat || 0.001
            const x = 8 + ((shop.lng - minLng) / rangeX) * 84
            const y = 8 + (1 - (shop.lat - minLat) / rangeY) * 76
            return (
              <div
                key={i}
                className={`shops-map-pin ${!shop.inStock ? 'shops-map-pin--oos' : ''}`}
                style={{ left: `${x}%`, top: `${y}%` }}
                title={`${shop.name} — ${shop.distance} km`}
              >
                <span className="shops-map-pin__dot" />
                <span className="shops-map-pin__label">{shop.distance} km</span>
              </div>
            )
          })}
          <div className="shops-map-you" style={{ left: '50%', top: '50%' }} title="Your location">
            <span />
          </div>
          <div className="shops-map-grid-overlay" />
        </div>

        <div className="shops-list">
          {shops.map((shop, i) => (
            <div key={i} className={`shops-item ${!shop.inStock ? 'shops-item--oos' : ''}`}>
              <div className="shops-item__icon" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"
                        fill={shop.inStock ? '#dbe6ff' : '#f3f4f6'}
                        stroke={shop.inStock ? '#2457d6' : '#9ca3af'} strokeWidth="1.4"/>
                  <circle cx="12" cy="9" r="2.5" fill={shop.inStock ? '#2457d6' : '#9ca3af'}/>
                </svg>
              </div>
              <div className="shops-item__body">
                <div className="shops-item__name">{shop.name}</div>
                <div className="shops-item__meta">
                  <span>{shop.area}</span>
                  <span className="shops-item__dot">·</span>
                  <span>{shop.distance} km away</span>
                  <span className="shops-item__dot">·</span>
                  <span className="shops-item__stars" title={`${shop.rating} / 5`}>
                    {starStr(shop.rating)} {shop.rating}
                  </span>
                </div>
                <div className="shops-item__stock">
                  {shop.inStock
                    ? <span className="shops-item__in-stock">
                        <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{marginRight:3,verticalAlign:'middle'}}>
                          <circle cx="6" cy="6" r="5" fill="#dcfce7"/>
                          <path d="M3.5 6l2 2 3-3" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                        In stock
                      </span>
                    : <span className="shops-item__oos">Out of stock</span>}
                </div>
              </div>
              <a
                className={`shops-item__dir-btn ${!shop.inStock ? 'shops-item__dir-btn--oos' : ''}`}
                href={mapsUrl(shop)}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Get directions to ${shop.name}`}
              >
                <svg width="12" height="12" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path d="M10 2l8 8-8 8M18 10H2" stroke="currentColor" strokeWidth="2"
                        strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Directions
              </a>
            </div>
          ))}
        </div>

        <div className="shops-modal__footer">
          <svg width="11" height="11" viewBox="0 0 16 16" fill="none" aria-hidden="true" style={{flexShrink:0}}>
            <circle cx="8" cy="8" r="6.5" stroke="#9ca3af" strokeWidth="1.2"/>
            <path d="M8 5v4M8 10.5v.5" stroke="#9ca3af" strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
          Locations are approximate. Directions open in Google Maps.
        </div>
      </div>
    </div>
  )
}

/* ─── Expiry badge ───────────────────────────────── */

function ExpiryBadge({ expiryDateStr, expiryUrgency }) {
  const dotMedium = (
    <svg width="9" height="9" viewBox="0 0 10 10" fill="none" aria-hidden="true">
      <circle cx="5" cy="5" r="4.5" fill="#fcd34d" stroke="#d97706" strokeWidth=".8"/>
    </svg>
  )
  const dotLow = (
    <svg width="9" height="9" viewBox="0 0 10 10" fill="none" aria-hidden="true">
      <circle cx="5" cy="5" r="4.5" fill="#86efac" stroke="#16a34a" strokeWidth=".8"/>
    </svg>
  )
  const cfg = {
    medium:  { cls: 'expiry-badge--medium', icon: dotMedium, label: `Exp: ${expiryDateStr}` },
    low:     { cls: 'expiry-badge--low',    icon: dotLow,    label: `Exp: ${expiryDateStr}` },
    minimal: { cls: 'expiry-badge--low',    icon: dotLow,    label: `Exp: ${expiryDateStr}` },
  }[expiryUrgency] || { cls: 'expiry-badge--low', icon: dotLow, label: `Exp: ${expiryDateStr}` }

  return (
    <span className={`expiry-badge ${cfg.cls}`} title={`Expiry date: ${expiryDateStr}`}>
      <span className="expiry-badge__icon">{cfg.icon}</span>
      {cfg.label}
    </span>
  )
}

/* ─── Single discount offer ──────────────────────── */

function DiscountOffer({ discount }) {
  const style = {
    medium:  { bg: '#fffbeb', border: '#fcd34d', color: '#92400e', pctColor: '#b45309' },
    low:     { bg: '#f0fdf4', border: '#86efac', color: '#166534', pctColor: '#15803d' },
    minimal: { bg: '#f0f7ff', border: '#bfdbfe', color: '#1e40af', pctColor: '#1d4ed8' },
  }[discount.urgency] || { bg: '#f0f7ff', border: '#bfdbfe', color: '#1e40af', pctColor: '#1d4ed8' }

  return (
    <div className="discount-offer" style={{ background: style.bg, borderColor: style.border }}>
      <span className="discount-offer__pct" style={{ color: style.pctColor }}>
        {discount.percent}% off
      </span>
      <span className="discount-offer__label" style={{ color: style.color }}>
        {discount.label}
      </span>
    </div>
  )
}

/* ─── Failed medicine panel (with manual re-search) ────────────────────── */

function FailedMedicinePanel({ medicine, onRetry }) {
  const [editName, setEditName]   = useState(medicine.original_name)
  const [loading,  setLoading]    = useState(false)
  const [error,    setError]      = useState(null)

  async function handleRetry(e) {
    e.preventDefault()
    if (!editName.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/v1/medicine/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ medicine_name: editName.trim(), generic_preference: true }),
      })
      if (!res.ok) throw new Error(await res.text())
      onRetry(await res.json(), editName.trim())
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rx-failed-panel surface">
      <div className="rx-failed-panel__icon" aria-hidden="true">
        <svg width="40" height="40" viewBox="0 0 48 48" fill="none">
          <circle cx="24" cy="24" r="20" fill="#fef3c7" stroke="#f59e0b" strokeWidth="1.5"/>
          <path d="M24 16v10M24 30v2" stroke="#92400e" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      </div>
      <h3 className="rx-failed-panel__heading">Could not identify medicine</h3>
      <p className="rx-failed-panel__sub">
        OCR extracted: <strong>{medicine.original_name}</strong>
      </p>
      {medicine.error && (
        <p className="rx-failed-panel__reason">{medicine.error}</p>
      )}

      <form className="rx-failed-panel__form" onSubmit={handleRetry}>
        <label className="rx-failed-panel__label" htmlFor="rx-retry-input">
          Edit name and retry
        </label>
        <div className="rx-failed-panel__input-row">
          <input
            id="rx-retry-input"
            className="rx-failed-panel__input"
            value={editName}
            onChange={e => setEditName(e.target.value)}
            placeholder="Enter medicine name…"
            disabled={loading}
            autoComplete="off"
          />
          <button
            type="submit"
            className="btn"
            disabled={loading || !editName.trim()}
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
        {error && (
          <div className="rx-failed-panel__error" role="alert">{error}</div>
        )}
      </form>
    </div>
  )
}

/* ─── Prescription-context badge shown on the medicine panels ──────────── */

function RxContextBadge({ medicine }) {
  const parts = []
  if (medicine.dosage)    parts.push(medicine.dosage)
  if (medicine.frequency) parts.push(medicine.frequency)
  if (medicine.duration)  parts.push(medicine.duration)
  if (medicine.dosage_form) parts.push(medicine.dosage_form)
  if (!parts.length) return null
  return (
    <div className="rx-context-badge">
      <svg width="11" height="11" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="3" y="2" width="10" height="12" rx="2" fill="#e0eaff" stroke="#3b82f6" strokeWidth="1.2"/>
        <path d="M5 5h6M5 8h4" stroke="#3b82f6" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
      <span>Prescribed: {parts.join(' · ')}</span>
    </div>
  )
}

/* ─── Inline recommendation view (reuses App.jsx visual patterns) ──────── */

function BulletList({ items, max, colorClass }) {
  const [expanded, setExpanded] = useState(false)
  if (!items?.length) return null
  const shown = max && !expanded ? items.slice(0, max) : items
  const rest  = max ? items.slice(max) : []
  return (
    <>
      <ul className={`ins-list ${colorClass || ''}`}>
        {shown.map((item, i) => <li key={i}>{item}</li>)}
      </ul>
      {rest.length > 0 && (
        <button className="ins-toggle" onClick={() => setExpanded(v => !v)}>
          <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            {expanded
              ? <path d="M2 8l4-4 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
              : <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>}
          </svg>
          {expanded ? 'Show less' : `+${rest.length} more`}
        </button>
      )}
    </>
  )
}

function MedicineInsightsBlock({ ins }) {
  if (!ins) return <div className="no-data-note">No AI insights available.</div>
  return (
    <div className="rx-insights">
      {ins.summary && (
        <div className="ins-block ins-block--summary">
          <div className="ins-block__header">
            <span className="ins-block__icon" aria-hidden="true">
              <svg width="11" height="11" viewBox="0 0 14 14" fill="none"><path d="M7 1l1.5 3.5L12 5l-2.5 2.5.6 3.5L7 9.5 3.9 11l.6-3.5L2 5l3.5-.5L7 1z" fill="#bfdbfe" stroke="#2457d6" strokeWidth="1" strokeLinejoin="round"/></svg>
            </span>
            <span className="ins-block__label">AI Summary</span>
          </div>
          <p className="ins-block__text">{ins.summary}</p>
        </div>
      )}
      {ins.key_uses?.length > 0 && (
        <div className="ins-block ins-block--uses">
          <div className="ins-block__header">
            <span className="ins-block__icon" aria-hidden="true">
              <svg width="11" height="11" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5" fill="#bbf7d0"/><path d="M3.5 6l2 2 3-3" stroke="#15803d" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </span>
            <span className="ins-block__label">Key Uses</span>
          </div>
          <div className="ins-chips">
            {ins.key_uses.map((u, i) => (
              <span key={i} className="ins-chip ins-chip--green">{u}</span>
            ))}
          </div>
        </div>
      )}
      {ins.important_safety_points?.length > 0 && (
        <div className="ins-block ins-block--safety">
          <div className="ins-block__header">
            <span className="ins-block__icon" aria-hidden="true">
              <svg width="11" height="11" viewBox="0 0 14 14" fill="none"><path d="M7 1L2 3.5v4C2 10.5 4.5 13 7 14c2.5-1 5-3.5 5-6.5v-4L7 1z" fill="#fcd34d" stroke="#d97706" strokeWidth="1"/><path d="M7 5v3M7 9.5v.5" stroke="#92400e" strokeWidth="1.2" strokeLinecap="round"/></svg>
            </span>
            <span className="ins-block__label">Key Safety Points</span>
          </div>
          <BulletList items={ins.important_safety_points} max={3} colorClass="list--amber" />
        </div>
      )}
      {ins.why_this_generic && (
        <div className="ins-block ins-block--summary" style={{background:'#f0fdf4',borderColor:'#bbf7d0'}}>
          <div className="ins-block__header">
            <span className="ins-block__icon" aria-hidden="true">
              <svg width="11" height="11" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="5" r="3" fill="#fef08a" stroke="#ca8a04" strokeWidth="1"/><path d="M7 9v3" stroke="#ca8a04" strokeWidth="1.2" strokeLinecap="round"/></svg>
            </span>
            <span className="ins-block__label" style={{color:'#15803d'}}>Why this generic?</span>
          </div>
          <p className="ins-block__text">{ins.why_this_generic}</p>
        </div>
      )}
    </div>
  )
}

function AltRowCompact({ alt, refPrice }) {
  const [open, setOpen]           = useState(false)
  const [showShops, setShowShops] = useState(false)

  const pct          = savePct(refPrice, alt.price)
  const priceDisplay = fmt(alt.price)
  const diffDisplay  = fmt(alt.price_difference)
  const ins          = alt.medicine_insights

  const dummy = useMemo(() => generateMedDummyData(alt.id ?? alt.name), [alt.id, alt.name])

  return (
    <>
      {showShops && (
        <ShopsMapModal
          shops={dummy.shops}
          medicineName={alt.name}
          onClose={() => setShowShops(false)}
        />
      )}

      <div className="alt-row">
        {/* ── Main row ── */}
        <div className="alt-row__main">
          <div className="alt-row__img" aria-hidden="true">
            <svg width="36" height="36" viewBox="0 0 48 48" fill="none">
              <rect x="8" y="14" width="32" height="20" rx="10" fill="#e0eaff" stroke="#3b82f6" strokeWidth="1.5"/>
              <rect x="8" y="20" width="32" height="8" fill="#bfdbfe" opacity="0.6"/>
            </svg>
          </div>
          <div className="alt-row__info" data-price={priceDisplay ? `₹${priceDisplay}` : ''}>
            <div className="alt-row__name">
              {alt.name}
              <GenericBadge isGeneric={alt.is_generic} />
            </div>
            {alt.manufacturer && (
              <div className="alt-row__manufacturer">{alt.manufacturer}</div>
            )}
            <div className="alt-row__specs">
              {alt.salt_composition && (
                <span className="spec-tag">
                  {/* Flask / molecule icon for salt/composition */}
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M9 3h6M10 3v6l-4 8a1 1 0 00.9 1.5h10.2a1 1 0 00.9-1.5L14 9V3" stroke="#6b7280" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    <path d="M8.5 16h7" stroke="#6b7280" strokeWidth="1.4" strokeLinecap="round"/>
                  </svg>
                  {alt.salt_composition}
                </span>
              )}
              {alt.dosage_form && (
                <span className="spec-tag">
                  {/* Capsule/pill icon for dosage form */}
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <rect x="3" y="8" width="18" height="8" rx="4" stroke="#6b7280" strokeWidth="1.8"/>
                    <line x1="12" y1="8" x2="12" y2="16" stroke="#6b7280" strokeWidth="1.4" strokeLinecap="round"/>
                  </svg>
                  {alt.dosage_form}
                </span>
              )}
              {alt.dosage && (
                <span className="spec-tag">
                  {/* Weight/scale icon for dosage amount */}
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M12 3v18M8 7l4-4 4 4" stroke="#6b7280" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  {alt.dosage}
                </span>
              )}
            </div>
          </div>
          <div className="alt-row__right">
            <div className="alt-row__price-block">
              {priceDisplay && <span className="alt-row__price">₹{priceDisplay}</span>}
              {diffDisplay && pct !== null && (
                <span className="alt-row__save-badge">Save ₹{diffDisplay} ({pct}%)</span>
              )}
            </div>
            <div className="alt-row__match-badges">
              {alt.same_salt   && <span className="match-badge match-badge--green"><CheckIcon />Same salt</span>}
              {alt.same_dosage && <span className="match-badge match-badge--green"><CheckIcon />Same dosage</span>}
            </div>
            <button className="view-details-btn" onClick={() => setOpen(v => !v)}>
              <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{marginRight:3}}>
                {open
                  ? <path d="M2 8l4-4 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                  : <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>}
              </svg>
              {open ? 'Hide' : 'Details'}
            </button>
          </div>
        </div>

        {/* ── Always-visible expiry + discount strip ── */}
        <div className="alt-row__expiry-strip">
          <ExpiryBadge
            expiryDateStr={dummy.expiryDateStr}
            expiryUrgency={dummy.expiryUrgency}
          />
          <DiscountOffer discount={dummy.discount} />
          <button
            className="shops-btn"
            onClick={() => setShowShops(true)}
            aria-label={`See nearby shops for ${alt.name}`}
          >
            <svg width="12" height="12" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="M10 2C6.69 2 4 4.69 4 8c0 4.67 6 10 6 10s6-5.33 6-10c0-3.31-2.69-6-6-6z"
                    fill="#dbe6ff" stroke="#2457d6" strokeWidth="1.5"/>
              <circle cx="10" cy="8" r="2" fill="#2457d6"/>
            </svg>
            Nearby shops
          </button>
        </div>

        {/* ── Expanded AI detail — animated via CSS ── */}
        <div className={`alt-row__detail${open ? ' alt-row__detail--open' : ''}`}>
          <div className="alt-row__detail__inner">
            <MedicineInsightsBlock ins={ins} />
          </div>
        </div>
      </div>
    </>
  )
}

/* ─── Why-section: structured reasoning (mirrors App.jsx) ────────────── */

function parseReasoning(text, alts) {
  if (!text) return { overview: '', perMed: [] }
  const sentences = text
    .split(/\n+/)
    .map(s => s.trim())
    .filter(Boolean)
  if (sentences.length <= 1) return { overview: text.trim(), perMed: [] }
  const [overview, ...rest] = sentences
  const perMed = rest.map(sentence => {
    const matched = alts.find(a =>
      sentence.toLowerCase().includes(a.name.toLowerCase())
    )
    return { name: matched?.name ?? null, sentence }
  })
  return { overview, perMed }
}

function WhySection({ reasoning, alts }) {
  const { overview, perMed } = parseReasoning(reasoning, alts || [])
  if (!overview && !perMed.length) return null
  return (
    <div className="why-section">
      <div className="why-section__header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{flexShrink:0}} aria-hidden="true">
          <path d="M12 2L4 6v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V6l-8-4z"
                fill="#dbe6ff" stroke="#2457d6" strokeWidth="1.5"/>
          <path d="M9 12l2 2 4-4" stroke="#2457d6" strokeWidth="1.8"
                strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        Why these alternatives?
      </div>
      <div className="why-section__body">
        {overview && (
          <p className="why-section__overview">{overview}</p>
        )}
        {perMed.length > 0 && (
          <ul className="why-section__permed">
            {perMed.map((item, i) => (
              <li key={i} className="why-section__permed-item">
                {item.name && (
                  <span className="why-section__medname">{item.name}</span>
                )}
                <span className="why-section__sentence">{item.sentence}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function RecommendationPanel({ medicine, recommendation }) {
  const ref  = recommendation.requested_medicine
  const alts = recommendation.recommended_alternatives
  const sv   = recommendation.safety_validation
  const why  = recommendation.llm_reasoning

  const [sortBy, setSortBy] = useState('price')
  const [showRefInsights, setShowRefInsights] = useState(false)

  const sorted = [...alts].sort((a, b) =>
    sortBy === 'price'
      ? parseFloat(a.price) - parseFloat(b.price)
      : parseFloat(b.price_difference) - parseFloat(a.price_difference)
  )

  const bannerParts = []
  if (sv?.same_salt   && ref.salt_composition) bannerParts.push(ref.salt_composition)
  if (sv?.same_dosage && ref.dosage)           bannerParts.push(`${ref.dosage} dosage`)

  return (
    <div className="rx-rec-panel">
      {/* ── Prescription context badge (dosage, frequency, duration) ── */}
      <RxContextBadge medicine={medicine} />

      {/* ── Requested medicine card ── */}
      <div className="rx-rec-panel__requested surface">
        <div className="rx-rec-panel__req-header">
          <div className="left-panel__header">
            <div className="med-icon">
              <svg width="28" height="28" viewBox="0 0 48 48" fill="none" aria-hidden="true">
                <rect x="8" y="14" width="32" height="20" rx="10" fill="#e0eaff" stroke="#3b82f6" strokeWidth="1.5"/>
                <rect x="8" y="20" width="32" height="8" fill="#bfdbfe" opacity="0.6"/>
              </svg>
            </div>
            <div className="left-panel__name-block">
              <div className="left-panel__name">{ref.name}</div>
              <div className="badge-row" style={{marginTop:2}}>
                <GenericBadge isGeneric={ref.is_generic} />
                <FdaBadge available={ref.fda_data_available} />
              </div>
              {ref.manufacturer && (
                <div className="left-panel__manufacturer">{ref.manufacturer}</div>
              )}
            </div>
          </div>
          <div className="rx-rec-panel__price-block">
            {fmt(ref.price) && (
              <span className="alt-row__price">₹{fmt(ref.price)}</span>
            )}
            <span className="fact-chip__label" style={{fontSize:10}}>MRP</span>
          </div>
        </div>
        <div className="left-panel__facts" style={{marginTop:6, gap:4}}>
          {ref.salt_composition && (
            <span className="fact-chip">
              <span className="fact-chip__icon" aria-hidden="true">
                <svg width="11" height="11" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" fill="#dbe6ff" stroke="#2457d6" strokeWidth="1.2"/><path d="M5 8h6M8 5v6" stroke="#2457d6" strokeWidth="1.4" strokeLinecap="round"/></svg>
              </span>
              {ref.salt_composition}
            </span>
          )}
          {ref.dosage_form && (
            <span className="fact-chip">
              <span className="fact-chip__icon" aria-hidden="true">
                <svg width="11" height="11" viewBox="0 0 16 16" fill="none"><rect x="3" y="2" width="10" height="12" rx="2" fill="#e0eaff" stroke="#3b82f6" strokeWidth="1.2"/><path d="M5 6h6M5 9h4" stroke="#3b82f6" strokeWidth="1.2" strokeLinecap="round"/></svg>
              </span>
              {ref.dosage_form}
            </span>
          )}
          {ref.dosage && (
            <span className="fact-chip">
              <span className="fact-chip__icon" aria-hidden="true">
                <svg width="11" height="11" viewBox="0 0 16 16" fill="none"><path d="M8 2v12M4 6l4-4 4 4" stroke="#6b7280" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </span>
              {ref.dosage}
            </span>
          )}
          {ref.medicine_insights && (
            <button className="view-details-btn" style={{marginLeft:'auto'}}
                    onClick={() => setShowRefInsights(v => !v)}>
              <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{marginRight:3}}>
                {showRefInsights
                  ? <path d="M2 8l4-4 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                  : <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>}
              </svg>
              {showRefInsights ? 'Hide info' : 'AI info'}
            </button>
          )}
        </div>
        {showRefInsights && <MedicineInsightsBlock ins={ref.medicine_insights} />}
      </div>

      {/* ── Alternatives ── */}
      <div className="rx-rec-panel__alts">
        <div className="rx-rec-panel__alts-header">
          <div>
            <div className="right-panel__title">Recommended alternatives</div>
            {bannerParts.length > 0 && (
              <div className="right-panel__subtitle">
                Same {bannerParts.join(' and ')}
              </div>
            )}
          </div>
          {alts.length > 1 && (
            <div className="sort-row">
              <span className="sort-label">Sort:</span>
              <button className={`sort-btn ${sortBy === 'price' ? 'sort-btn--active' : ''}`}
                      onClick={() => setSortBy('price')}>Price</button>
              <button className={`sort-btn ${sortBy === 'savings' ? 'sort-btn--active' : ''}`}
                      onClick={() => setSortBy('savings')}>Savings</button>
            </div>
          )}
        </div>

        {bannerParts.length > 0 && (
          <div className="safety-banner">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 2L4 6v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V6l-8-4z"
                    fill="#dcfce7" stroke="#16a34a" strokeWidth="1.5"/>
              <path d="M9 12l2 2 4-4" stroke="#16a34a" strokeWidth="1.8"
                    strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            All alternatives contain the same {bannerParts.join(' and ')}
          </div>
        )}

        {/* ── Why section — pinned above the scrollable alt list ── */}
        {why && (
          <div className="rx-rec-panel__why">
            <WhySection reasoning={why} alts={alts} />
          </div>
        )}

        {alts.length === 0 ? (
          <div className="empty-state">No cheaper alternatives found in the database.</div>
        ) : (
          <div className="rx-rec-panel__alt-list">
            {sorted.map(alt => (
              <AltRowCompact key={alt.id} alt={alt} refPrice={ref.price} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── Main PrescriptionResults component ────────────────────────────────── */

/**
 * PrescriptionResults
 * -------------------
 * Full-page results view for a prescription analysis.
 * Layout: summary topbar → sidebar (medicine list) + main panel (recommendation).
 *
 * Props
 * -----
 * data    : PrescriptionAnalysisResponse
 * onBack  : () => void
 */
export default function PrescriptionResults({ data, onBack }) {
  const [selectedIdx, setSelectedIdx] = useState(0)

  // Allow the failed-panel retry to inject a real recommendation into the list
  const [overrides, setOverrides] = useState({})   // { [idx]: RecommendationResponse }

  const medicines = data.medicines || []
  const selected  = medicines[selectedIdx]

  function handleRetry(recommendation, resolvedName) {
    setOverrides(prev => ({
      ...prev,
      [selectedIdx]: { recommendation, resolvedName },
    }))
  }

  // Merge override into selected medicine
  const override = overrides[selectedIdx]
  const effectiveRec   = override?.recommendation ?? selected?.recommendation
  const effectiveName  = override?.resolvedName   ?? selected?.matched_name ?? selected?.original_name
  const effectiveMatch = override != null ? true : selected?.matched

  return (
    <div className="rx-results">
      {/* ── Topbar ── */}
      <div className="rx-results__topbar results-topbar">
        <button className="back-btn" onClick={onBack} aria-label="Back to search">
          <svg width="15" height="15" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M13 4l-6 6 6 6" stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back to search
        </button>
        <div className="topbar-title">
          <span>genRx — Prescription</span>
          <span className="topbar-badge">
            <svg width="11" height="11" viewBox="0 0 16 16" fill="none" style={{marginRight:4}} aria-hidden="true">
              <path d="M8 1L2 4v4c0 3.7 2.56 7.16 6 8 3.44-.84 6-4.3 6-8V4L8 1z"
                    fill="#dcfce7" stroke="#16a34a" strokeWidth="1.2"/>
              <path d="M5.5 8l2 2 3-3" stroke="#16a34a" strokeWidth="1.5"
                    strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            AI-powered OCR · alternatives matched by safety and price
          </span>
        </div>
      </div>

      {/* ── Body: sidebar + main panel ── */}
      {medicines.length > 0 ? (
        <div className="rx-results__body">
          {/* ── Left column: summary + sidebar ── */}
          <div className="rx-results__left">
            <PrescriptionSummary
              summary={data.summary}
              patientName={data.patient_name}
              doctor={data.doctor}
              date={data.date}
            />
            <PrescriptionSidebar
              medicines={medicines}
              selectedIndex={selectedIdx}
              onSelect={setSelectedIdx}
            />
          </div>
          <main className="rx-results__main">
            {selected && (
              <>
                <div className="rx-results__medicine-label">
                  {effectiveName}
                  {selected.confidence > 0 && (
                    <span className="rx-results__confidence">
                      {Math.round(selected.confidence * 100)}% OCR confidence
                    </span>
                  )}
                </div>

                {effectiveMatch && effectiveRec ? (
                  <RecommendationPanel
                    medicine={selected}
                    recommendation={effectiveRec}
                  />
                ) : (
                  <FailedMedicinePanel
                    medicine={{ ...selected, original_name: effectiveName }}
                    onRetry={handleRetry}
                  />
                )}
              </>
            )}
          </main>
        </div>
      ) : (
        <div className="surface rx-results__empty">
          <p>No medicines were detected in this prescription.</p>
          <p className="no-data-note">Please ensure the image is clear and contains a printed or handwritten medicine list.</p>
        </div>
      )}
    </div>
  )
}

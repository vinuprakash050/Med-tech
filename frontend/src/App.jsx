import React, { useEffect, useMemo, useRef, useState } from 'react'
import PrescriptionUpload  from './PrescriptionUpload.jsx'
import PrescriptionResults from './PrescriptionResults.jsx'
import { generateMedDummyData } from './dummyMedData.js'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

/* ─── Helpers ─────────────────────────────────────── */

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
    const data = JSON.parse(raw)
    if (typeof data.detail === 'string') return data.detail
  } catch {
    // Fall through to a compact generic message below.
  }
  if (raw.toLowerCase().includes('openrouter') || raw.toLowerCase().includes('llm')) {
    return 'AI service is temporarily unavailable. Please try again in a moment.'
  }
  return raw.replace(/^Error:\s*/, '')
}

/* ─── Badges ──────────────────────────────────────── */

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

function VendorMetric({ label, value, hint }) {
  return (
    <div className="vendor-metric">
      <div className="vendor-metric__value">{value}</div>
      <div className="vendor-metric__label">{label}</div>
      {hint && <div className="vendor-metric__hint">{hint}</div>}
    </div>
  )
}

function VendorView({ onBackToSearch, dashboard, loading, error, refresh }) {
  const medicines = dashboard?.medicines || []
  const summary = dashboard?.summary
  const PAGE_SIZE = 3
  const [page, setPage] = useState(1)
  const totalPages = Math.ceil(medicines.length / PAGE_SIZE)
  const paginated = medicines.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <div className="vendor-view">
      <div className="vendor-hero surface">
        <div>
          <p className="eyebrow">Vendor dashboard</p>
          <h1>Expiry-aware discount planner</h1>
          <p className="hero-copy">
            genRx vendor view — prioritise clearance using real stock, expiry, and sales signals to set the right discount before medicines expire.
          </p>
        </div>
        <div className="vendor-hero__actions">
          <button className="btn btn--ghost" onClick={onBackToSearch}>Back to search</button>
          <button
            className="btn btn--devices"
            onClick={() => { window.location.hash = '#vendor-devices' }}
          >
            <svg width="13" height="13" viewBox="0 0 20 20" fill="none" aria-hidden="true" style={{marginRight:5}}>
              <rect x="3" y="3" width="14" height="14" rx="3" fill="none" stroke="currentColor" strokeWidth="1.7"/>
              <path d="M7 10h6M10 7v6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/>
            </svg>
            Device Feedback
          </button>
          <button className="btn" onClick={refresh} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh insights'}
          </button>
        </div>
      </div>

      <div className="vendor-summary-grid">
        <VendorMetric label="Medicines tracked" value={String(summary?.medicines_tracked || 0)} hint="Curated from user-facing catalog" />
        <VendorMetric label="Expiring within 30 days" value={String(summary?.expiring_within_30_days || 0)} hint="Push these first" />
        <VendorMetric label="Clearance candidates" value={String(summary?.clearance_candidates || 0)} hint="Need a stronger discount" />
        <VendorMetric label="Avg suggested discount" value={`${summary?.avg_suggested_discount || 0}%`} hint={`Inventory stock: ${summary?.total_stock || 0}`} />
      </div>

      <div className="vendor-layout">
        <section className="vendor-panel surface">
          <div className="vendor-panel__header">
            <div>
              <div className="vendor-panel__eyebrow">Inventory board</div>
              <div className="vendor-panel__title">
                {medicines.length} medicines with expiry and sales history
              </div>
            </div>
            <div className="vendor-panel__chip">Dummy JSON data</div>
          </div>

          <div className="vendor-grid">
            {paginated.map(item => {
              const recommendation = item.recommendation
              const urgencyClass =
                recommendation?.days_left <= 7 ? 'is-urgent' :
                recommendation?.days_left <= 30 ? 'is-warning' :
                'is-safe'
              return (
                <article key={item.id} className={`vendor-card ${urgencyClass}`}>
                  <div className="vendor-card__top">
                    <div>
                      <h3>{item.name}</h3>
                      <p>{item.brand} · {item.category}</p>
                    </div>
                    <span className={`vendor-badge vendor-badge--${urgencyClass}`}>
                      {recommendation ? item.urgency_label : 'Loading AI'}
                    </span>
                  </div>

                  <div className="vendor-card__facts">
                    <span>Expiry: <strong>{item.expiry_date}</strong></span>
                    <span>{recommendation ? `${recommendation.days_left} days left` : 'Loading recommendation...'}</span>
                    <span>Stock: {item.stock}</span>
                  </div>

                  <div className="vendor-card__stats">
                    <div>
                      <span>Sales 7d</span>
                      <strong>{item.previous_sales_7_days}</strong>
                    </div>
                    <div>
                      <span>Sales 30d</span>
                      <strong>{item.previous_sales_30_days}</strong>
                    </div>
                    <div>
                      <span>Margin</span>
                      <strong>{item.margin_percent}%</strong>
                    </div>
                  </div>

                  <div className="vendor-card__recommendation">
                    {recommendation ? (
                      <>
                        <div className="vendor-card__discount">{recommendation.discount_percent}% off</div>
                        <div className="vendor-card__agent-line">
                          <span>AI agent</span>
                          <strong>{recommendation.action}</strong>
                          <em>{recommendation.confidence} confidence</em>
                        </div>
                        <p>{recommendation.reason}</p>
                      </>
                    ) : (
                      <p>Loading AI recommendation...</p>
                    )}
                  </div>
                </article>
              )
            })}
          </div>

          {/* ── Pagination ── */}
          {totalPages > 1 && (
            <div className="vendor-pagination">
              <button
                className="vendor-pg-btn"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                aria-label="Previous page"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>

              {Array.from({ length: totalPages }, (_, i) => i + 1).map(n => (
                <button
                  key={n}
                  className={`vendor-pg-btn ${n === page ? 'vendor-pg-btn--active' : ''}`}
                  onClick={() => setPage(n)}
                  aria-label={`Page ${n}`}
                  aria-current={n === page ? 'page' : undefined}
                >
                  {n}
                </button>
              ))}

              <button
                className="vendor-pg-btn"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                aria-label="Next page"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  <path d="M5 2l5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>

              <span className="vendor-pg-info">
                Page {page} of {totalPages} · {medicines.length} total
              </span>
            </div>
          )}

          {error && <div className="vendor-error">{error}</div>}
          {loading && !medicines.length && <div className="vendor-empty">Loading vendor dashboard…</div>}
        </section>

        <aside className="vendor-side surface">
          <div className="vendor-panel__header">
            <div>
              <div className="vendor-panel__eyebrow">AI logic</div>
              <div className="vendor-panel__title">How the discount is chosen</div>
            </div>
          </div>

          <div className="vendor-insight">
            <h4>What the model uses</h4>
            <ul>
              <li>Expiry date and days left</li>
              <li>7-day and 30-day sales count</li>
              <li>Stock level versus recent movement</li>
              <li>Margin guardrails so discount stays realistic</li>
            </ul>
          </div>

          <div className="vendor-insight vendor-insight--accent">
            <h4>Suggested rule set</h4>
            <p>If expiry is within 7 days, push 25%+.</p>
            <p>Within 30 days, use a 10-20% clearance discount.</p>
            <p>If sales are slow but expiry is far away, keep it light.</p>
            <p>The agent combines expiry pressure, recent sales, and stock depth before suggesting a discount.</p>
          </div>

          <div className="vendor-insight">
            <h4>Why this is valid data</h4>
            <p>
              These fields can come from stock entry, batch tracking, billing history,
              and order history, so they are realistic to collect later.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}

/* ─── Shops Map Modal ────────────────────────────── */

function ShopsMapModal({ shops, medicineName, onClose }) {
  // Close on Escape key
  useEffect(() => {
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
        {/* Header */}
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

        {/* Map-like visual grid */}
        <div className="shops-map-canvas" aria-hidden="true">
          {shops.map((shop, i) => {
            /* normalise lat/lng offset to a [5%…90%] position inside the canvas */
            const lats  = shops.map(s => s.lat)
            const lngs  = shops.map(s => s.lng)
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
          {/* "You are here" marker */}
          <div className="shops-map-you" style={{ left: '50%', top: '50%' }} title="Your location">
            <span />
          </div>
          <div className="shops-map-grid-overlay" aria-hidden="true" />
        </div>

        {/* Shop list */}
        <div className="shops-list">
          {shops.map((shop, i) => (
            <div key={i} className={`shops-item ${!shop.inStock ? 'shops-item--oos' : ''}`}>
              <div className="shops-item__icon" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"
                        fill={shop.inStock ? '#dbe6ff' : '#f3f4f6'} stroke={shop.inStock ? '#2457d6' : '#9ca3af'} strokeWidth="1.4"/>
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
  const cfg = {
    medium:  {
      cls: 'expiry-badge--medium',
      icon: (
        <svg width="9" height="9" viewBox="0 0 10 10" fill="none" aria-hidden="true">
          <circle cx="5" cy="5" r="4.5" fill="#fcd34d" stroke="#d97706" strokeWidth=".8"/>
        </svg>
      ),
      label: `Exp: ${expiryDateStr}`,
    },
    low:     {
      cls: 'expiry-badge--low',
      icon: (
        <svg width="9" height="9" viewBox="0 0 10 10" fill="none" aria-hidden="true">
          <circle cx="5" cy="5" r="4.5" fill="#86efac" stroke="#16a34a" strokeWidth=".8"/>
        </svg>
      ),
      label: `Exp: ${expiryDateStr}`,
    },
    minimal: {
      cls: 'expiry-badge--low',
      icon: (
        <svg width="9" height="9" viewBox="0 0 10 10" fill="none" aria-hidden="true">
          <circle cx="5" cy="5" r="4.5" fill="#86efac" stroke="#16a34a" strokeWidth=".8"/>
        </svg>
      ),
      label: `Exp: ${expiryDateStr}`,
    },
  }[expiryUrgency] || {
    cls: 'expiry-badge--low',
    icon: (
      <svg width="9" height="9" viewBox="0 0 10 10" fill="none" aria-hidden="true">
        <circle cx="5" cy="5" r="4.5" fill="#86efac" stroke="#16a34a" strokeWidth=".8"/>
      </svg>
    ),
    label: `Exp: ${expiryDateStr}`,
  }

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

/* ─── Bullet list with expand ─────────────────────── */

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

/* ─── Left panel: Searched medicine ──────────────── */

function SearchedMedicinePanel({ medicine }) {
  const ins = medicine.medicine_insights
  const [showMore, setShowMore] = useState(false)

  const hasBelow = ins && (
    ins.emergency_warnings?.length > 0 ||
    ins.who_should_be_careful?.length > 0 ||
    ins.possible_side_effects?.length > 0 ||
    ins.pregnancy_breastfeeding
  )

  const priceDisplay = fmt(medicine.price)

  return (
    <div className="left-panel">
      {/* ── Static (pinned) header ── */}
      <div className="left-panel__static">
        <div className="left-panel__header">
          <div className="med-icon">
            <svg width="40" height="40" viewBox="0 0 48 48" fill="none" aria-hidden="true">
              <rect x="8" y="14" width="32" height="20" rx="10" fill="#e0eaff" stroke="#3b82f6" strokeWidth="1.5"/>
              <rect x="8" y="20" width="32" height="8" fill="#bfdbfe" opacity="0.6"/>
            </svg>
          </div>
          <div className="left-panel__name-block">
            <div className="left-panel__name">{medicine.name}</div>
            <div className="badge-row" style={{ marginTop: 3 }}>
              <GenericBadge isGeneric={medicine.is_generic} />
              <FdaBadge available={medicine.fda_data_available} />
            </div>
            {medicine.manufacturer && (
              <div className="left-panel__manufacturer">{medicine.manufacturer}</div>
            )}
          </div>
        </div>

        <div className="left-panel__facts">
          {medicine.salt_composition && (
            <div className="fact-chip">
              <span className="fact-chip__icon" aria-hidden="true">
                <svg width="11" height="11" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" fill="#dbe6ff" stroke="#2457d6" strokeWidth="1.2"/><path d="M5 8h6M8 5v6" stroke="#2457d6" strokeWidth="1.4" strokeLinecap="round"/></svg>
              </span>
              <span>{medicine.salt_composition}</span>
            </div>
          )}
          {medicine.dosage_form && (
            <div className="fact-chip">
              <span className="fact-chip__icon" aria-hidden="true">
                <svg width="11" height="11" viewBox="0 0 16 16" fill="none"><rect x="3" y="2" width="10" height="12" rx="2" fill="#e0eaff" stroke="#3b82f6" strokeWidth="1.2"/><path d="M5 6h6M5 9h4" stroke="#3b82f6" strokeWidth="1.2" strokeLinecap="round"/></svg>
              </span>
              <span>{medicine.dosage_form}</span>
            </div>
          )}
          {medicine.dosage && (
            <div className="fact-chip">
              <span className="fact-chip__icon" aria-hidden="true">
                <svg width="11" height="11" viewBox="0 0 16 16" fill="none"><path d="M8 2v12M4 6l4-4 4 4" stroke="#6b7280" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </span>
              <span>{medicine.dosage}</span>
            </div>
          )}
          {priceDisplay && (
            <div className="fact-chip fact-chip--price">
              <span>₹{priceDisplay}</span>
              <span className="fact-chip__label">MRP</span>
            </div>
          )}
        </div>

        <div className="ref-medicine-label">
          <span className="ref-dot" /> Reference medicine
        </div>
      </div>

      {/* ── Scrollable insights area ── */}
      <div className="left-panel__scroll">
        {ins?.summary && (
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

        {ins?.key_uses?.length > 0 && (
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

        {ins?.important_safety_points?.length > 0 && (
          <div className="ins-block ins-block--safety">
            <div className="ins-block__header">
              <span className="ins-block__icon" aria-hidden="true">
                <svg width="11" height="11" viewBox="0 0 14 14" fill="none"><path d="M7 1L2 3.5v4C2 10.5 4.5 13 7 14c2.5-1 5-3.5 5-6.5v-4L7 1z" fill="#fcd34d" stroke="#d97706" strokeWidth="1"/><path d="M7 5v3M7 9.5v.5" stroke="#92400e" strokeWidth="1.2" strokeLinecap="round"/></svg>
              </span>
              <span className="ins-block__label">Key Safety Points</span>
            </div>
            <BulletList items={ins.important_safety_points} max={4} colorClass="list--amber" />
          </div>
        )}

        {hasBelow && (
          <button className="view-safety-btn" onClick={() => setShowMore(v => !v)}>
            <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{marginRight:4}}>
              {showMore
                ? <path d="M2 8l4-4 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                : <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>}
            </svg>
            {showMore ? 'Hide full safety info' : 'View full safety information'}
          </button>
        )}

        {showMore && ins && (
          <>
            {ins.emergency_warnings?.length > 0 && (
              <div className="ins-block ins-block--emergency">
                <div className="ins-block__header">
                  <span className="ins-block__icon" aria-hidden="true">
                    <svg width="11" height="11" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" fill="#fca5a5" stroke="#dc2626" strokeWidth="1"/><path d="M7 4v4M7 9.5v.5" stroke="#991b1b" strokeWidth="1.4" strokeLinecap="round"/></svg>
                  </span>
                  <span className="ins-block__label">Emergency Warnings</span>
                </div>
                <BulletList items={ins.emergency_warnings} colorClass="list--red" />
              </div>
            )}
            {ins.who_should_be_careful?.length > 0 && (
              <div className="ins-block ins-block--careful">
                <div className="ins-block__header">
                  <span className="ins-block__icon" aria-hidden="true">
                    <svg width="11" height="11" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="4.5" r="2" fill="#d8b4fe" stroke="#7c3aed" strokeWidth="1"/><path d="M3 12c0-2.2 1.8-4 4-4s4 1.8 4 4" stroke="#7c3aed" strokeWidth="1.2" strokeLinecap="round"/></svg>
                  </span>
                  <span className="ins-block__label">Who Should Be Careful</span>
                </div>
                <BulletList items={ins.who_should_be_careful} colorClass="list--purple" />
              </div>
            )}
            {ins.possible_side_effects?.length > 0 && (
              <div className="ins-block ins-block--side">
                <div className="ins-block__header">
                  <span className="ins-block__icon" aria-hidden="true">
                    <svg width="11" height="11" viewBox="0 0 14 14" fill="none"><path d="M7 1L1 12h12L7 1z" fill="#fed7aa" stroke="#ea580c" strokeWidth="1"/><path d="M7 6v3M7 10.5v.5" stroke="#9a3412" strokeWidth="1.2" strokeLinecap="round"/></svg>
                  </span>
                  <span className="ins-block__label">Possible Side Effects</span>
                </div>
                <BulletList items={ins.possible_side_effects} colorClass="list--orange" />
              </div>
            )}
            {ins.pregnancy_breastfeeding && (
              <div className="ins-block ins-block--preg">
                <div className="ins-block__header">
                  <span className="ins-block__icon" aria-hidden="true">
                    <svg width="11" height="11" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="4" r="2.5" fill="#f0abfc" stroke="#a21caf" strokeWidth="1"/><ellipse cx="7" cy="10" rx="3.5" ry="2.5" fill="#fdf2f8" stroke="#a21caf" strokeWidth="1"/></svg>
                  </span>
                  <span className="ins-block__label">Pregnancy &amp; Breastfeeding</span>
                </div>
                <p className="ins-block__text">{ins.pregnancy_breastfeeding}</p>
              </div>
            )}
          </>
        )}

        {!ins && (
          <div className="no-data-note">No AI insights available for this medicine.</div>
        )}
      </div>
    </div>
  )
}

/* ─── Right panel: Single alternative row ─────────── */

function AltRow({ alt, refPrice }) {
  const [open, setOpen]           = useState(false)
  const [showShops, setShowShops] = useState(false)

  const ins          = alt.medicine_insights
  const pct          = savePct(refPrice, alt.price)
  const priceDisplay = fmt(alt.price)
  const diffDisplay  = fmt(alt.price_difference)

  // Deterministic dummy data keyed to this medicine
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
        <div className="alt-row__main">
          {/* Icon */}
          <div className="alt-row__img" aria-hidden="true">
            <svg width="36" height="36" viewBox="0 0 48 48" fill="none">
              <rect x="8" y="14" width="32" height="20" rx="10" fill="#e0eaff" stroke="#3b82f6" strokeWidth="1.5"/>
              <rect x="8" y="20" width="32" height="8" fill="#bfdbfe" opacity="0.6"/>
            </svg>
          </div>

          {/* Name + manufacturer + specs */}
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
                <span className="spec-tag">{alt.dosage}</span>
              )}
            </div>
          </div>

          {/* Price + match badges + action */}
          <div className="alt-row__right">
            <div className="alt-row__price-block">
              {priceDisplay && (
                <span className="alt-row__price">₹{priceDisplay}</span>
              )}
              {diffDisplay && pct !== null && (
                <span className="alt-row__save-badge">
                  Save ₹{diffDisplay} ({pct}%)
                </span>
              )}
              {fmt(refPrice) && (
                <span className="alt-row__mrp">MRP ₹{fmt(refPrice)}</span>
              )}
            </div>

            <div className="alt-row__match-badges">
              {alt.same_salt === true && (
                <span className="match-badge match-badge--green">
                  <CheckIcon /> Same salt composition
                </span>
              )}
              {alt.same_salt === false && (
                <span className="match-badge match-badge--amber">
                  Different salt composition
                </span>
              )}
              {alt.same_dosage === true && (
                <span className="match-badge match-badge--green">
                  <CheckIcon /> Same dosage
                </span>
              )}
              {alt.same_dosage === false && (
                <span className="match-badge match-badge--amber">
                  Different dosage
                </span>
              )}
            </div>

            <button className="view-details-btn" onClick={() => setOpen(v => !v)}>
              <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{marginRight:3}}>
                {open
                  ? <path d="M2 8l4-4 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                  : <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>}
              </svg>
              {open ? 'Hide details' : 'View details'}
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

        {/* ── Expanded AI detail — transitions via .alt-row__detail--open ── */}
        <div className={`alt-row__detail${open ? ' alt-row__detail--open' : ''}`}>
          <div className="alt-row__detail__inner">
            {ins?.summary && (
              <div className="alt-detail-section">
                <div className="alt-detail-section__label">
                  <svg width="10" height="10" viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M7 1l1.5 3.5L12 5l-2.5 2.5.6 3.5L7 9.5 3.9 11l.6-3.5L2 5l3.5-.5L7 1z" fill="#bfdbfe" stroke="#2457d6" strokeWidth="1" strokeLinejoin="round"/></svg>
                  AI Summary
                </div>
                <p className="alt-detail-text">{ins.summary}</p>
              </div>
            )}
            {ins?.key_uses?.length > 0 && (
              <div className="alt-detail-section">
                <div className="alt-detail-section__label">
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="#bbf7d0"/><path d="M3.5 6l2 2 3-3" stroke="#15803d" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  Uses
                </div>
                <BulletList items={ins.key_uses} max={4} colorClass="list--green" />
              </div>
            )}
            {ins?.important_safety_points?.length > 0 && (
              <div className="alt-detail-section">
                <div className="alt-detail-section__label">
                  <svg width="10" height="10" viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M7 1L2 3.5v4C2 10.5 4.5 13 7 14c2.5-1 5-3.5 5-6.5v-4L7 1z" fill="#fcd34d" stroke="#d97706" strokeWidth="1"/><path d="M7 5v3M7 9.5v.5" stroke="#92400e" strokeWidth="1.2" strokeLinecap="round"/></svg>
                  Key Safety
                </div>
                <BulletList items={ins.important_safety_points} max={3} colorClass="list--amber" />
              </div>
            )}
            {ins?.why_this_generic && (
              <div className="alt-detail-section">
                <div className="alt-detail-section__label">
                  <svg width="10" height="10" viewBox="0 0 14 14" fill="none" aria-hidden="true"><circle cx="7" cy="5" r="3" fill="#fef08a" stroke="#ca8a04" strokeWidth="1"/><path d="M7 9v3" stroke="#ca8a04" strokeWidth="1.2" strokeLinecap="round"/></svg>
                  Why this generic?
                </div>
                <p className="alt-detail-text">{ins.why_this_generic}</p>
              </div>
            )}
            {!ins && (
              <p className="alt-detail-text no-data-note">No AI insights available.</p>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

/* small reusable check icon */
function CheckIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{marginRight:3,flexShrink:0}}>
      <circle cx="6" cy="6" r="5" fill="#dcfce7"/>
      <path d="M3.5 6l2 2 3-3" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

/* ─── Why-section: structured reasoning ──────────── */

function WhySection({ reasoning, accent }) {
  if (!reasoning || !reasoning.trim()) return null
  // Flatten all newlines into a single sentence run, then trim to ~300 chars
  const text = reasoning.replace(/\n+/g, ' ').trim()

  return (
    <div className="why-section">
      <div className="why-section__header">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{flexShrink:0}} aria-hidden="true">
          <path d="M12 2L4 6v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V6l-8-4z"
                fill={accent ? '#dbe6ff' : '#dcfce7'} stroke={accent ? '#2457d6' : '#16a34a'} strokeWidth="1.5"/>
          <path d="M9 12l2 2 4-4" stroke={accent ? '#2457d6' : '#16a34a'} strokeWidth="1.8"
                strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        Why these alternatives?
      </div>
      <div className="why-section__body">
        <p className="why-section__overview">{text}</p>
      </div>
    </div>
  )
}

/* ─── Right panel: Alternatives list ─────────────── */

function AlternativesPanel({ result }) {
  const ref    = result.requested_medicine
  const alts   = result.recommended_alternatives
  const sv     = result.safety_validation   // { same_salt, same_dosage }
  const reasoning = result.llm_reasoning

  const [sortBy, setSortBy] = useState('price')

  const sorted = [...alts].sort((a, b) => {
    if (sortBy === 'price')   return parseFloat(a.price) - parseFloat(b.price)
    if (sortBy === 'savings') return parseFloat(b.price_difference) - parseFloat(a.price_difference)
    return 0
  })

  // Build safety banner text only from actual API data
  const bannerParts = []
  if (sv?.same_salt    && ref.salt_composition) bannerParts.push(ref.salt_composition)
  if (sv?.same_dosage  && ref.dosage)           bannerParts.push(`${ref.dosage} dosage`)

  return (
    <div className="right-panel">
      {/* ── Pinned top: title + sort + banner ── */}
      <div className="right-panel__top">
        <div className="right-panel__header">
          <div>
            <div className="right-panel__title">Recommended alternatives</div>
            {bannerParts.length > 0 && (
              <div className="right-panel__subtitle">
                Lower price alternatives with the same {bannerParts.join(' and ')}
              </div>
            )}
          </div>
          {alts.length > 1 && (
            <div className="sort-row">
              <span className="sort-label">Sort by:</span>
              <button
                className={`sort-btn ${sortBy === 'price' ? 'sort-btn--active' : ''}`}
                onClick={() => setSortBy('price')}
              >
                Price {sortBy === 'price' ? (
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{marginLeft:2,verticalAlign:'middle'}}>
                    <path d="M6 2v8M3 7l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                ) : ''}
              </button>
              <button
                className={`sort-btn ${sortBy === 'savings' ? 'sort-btn--active' : ''}`}
                onClick={() => setSortBy('savings')}
              >
                Savings {sortBy === 'savings' ? (
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{marginLeft:2,verticalAlign:'middle'}}>
                    <path d="M6 10V2M3 5l3-3 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                ) : ''}
              </button>
            </div>
          )}
        </div>

        {bannerParts.length > 0 && (
          <div className="safety-banner">
            <ShieldCheckIcon />
            All alternatives contain the same {bannerParts.join(' and ')}
          </div>
        )}
      </div>

      {/* ── Scrollable alt list ── */}
      <div className="alt-rows-scroll">
        {alts.length === 0 ? (
          <div className="empty-state">No cheaper alternatives found in the database.</div>
        ) : (
          sorted.map(alt => (
            <AltRow key={alt.id} alt={alt} refPrice={ref.price} />
          ))
        )}
      </div>

      {/* ── Pinned bottom: Why section ── */}
      {reasoning && (
        <div className="right-panel__bottom">
          <WhySection reasoning={reasoning} accent />
        </div>
      )}
    </div>
  )
}

function ShieldCheckIcon({ accent }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{flexShrink:0}} aria-hidden="true">
      <path
        d="M12 2L4 6v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V6l-8-4z"
        fill={accent ? '#dbe6ff' : '#dcfce7'}
        stroke={accent ? '#2457d6' : '#16a34a'}
        strokeWidth="1.5"
      />
      <path
        d="M9 12l2 2 4-4"
        stroke={accent ? '#2457d6' : '#16a34a'}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/* ─── Results view ────────────────────────────────── */

function ResultsView({ result, onBack }) {
  const ref = result.requested_medicine
  const sv  = result.safety_validation

  // Topbar hint — only from actual data
  const topbarParts = []
  if (sv?.same_salt && ref.salt_composition)  topbarParts.push(ref.salt_composition)
  if (sv?.same_dosage && ref.dosage)          topbarParts.push(`same dosage`)

  return (
    <div className="results-view">
      <div className="results-topbar">
        <button className="back-btn" onClick={onBack} aria-label="Back to search">
          <svg width="15" height="15" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M13 4l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back to search
        </button>
        <div className="topbar-title">
          <span>genRx</span>
          <span className="topbar-badge">
            <svg width="11" height="11" viewBox="0 0 16 16" fill="none" style={{marginRight:4}} aria-hidden="true">
              <path d="M8 1L2 4v4c0 3.7 2.56 7.16 6 8 3.44-.84 6-4.3 6-8V4L8 1z" fill="#dcfce7" stroke="#16a34a" strokeWidth="1.2"/>
              <path d="M5.5 8l2 2 3-3" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            AI-powered safety and price recommendations
          </span>
        </div>
        {topbarParts.length > 0 && (
          <div className="topbar-right">
            <span className="topbar-hint">All alternatives contain the same {topbarParts.join(' and ')}</span>
          </div>
        )}
      </div>

      <div className="results-columns">
        <div className="results-left">
          <div className="column-label">Your searched medicine</div>
          <SearchedMedicinePanel medicine={ref} />
        </div>
        <div className="results-right">
          <AlternativesPanel result={result} />
        </div>
      </div>
    </div>
  )
}

/* ─── Device icon ─────────────────────────────────── */

function DeviceIcon({ type, size = 38 }) {
  if (type === 'pacemaker') {
    return (
      <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <rect x="10" y="10" width="28" height="28" rx="7" fill="#fce7f3" stroke="#db2777" strokeWidth="1.6"/>
        <path d="M16 24h4l3-6 4 12 3-6h6" stroke="#db2777" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    )
  }
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <ellipse cx="24" cy="26" rx="10" ry="7" fill="#dbeafe" stroke="#2563eb" strokeWidth="1.6"/>
      <path d="M14 26 Q12 16 24 14 Q36 16 34 26" stroke="#2563eb" strokeWidth="1.6" fill="none"/>
      <circle cx="24" cy="14" r="2.5" fill="#2563eb"/>
      <path d="M21 14 Q20 8 24 8 Q28 8 27 14" stroke="#2563eb" strokeWidth="1.4" fill="none"/>
    </svg>
  )
}

/* ─── Star rating display ──────────────────────────── */

function StarRating({ rating }) {
  const full  = Math.floor(rating)
  const half  = (rating - full) >= 0.5
  const empty = 5 - full - (half ? 1 : 0)
  return (
    <span className="star-rating" aria-label={`${rating} out of 5`}>
      {'★'.repeat(full)}
      {half ? '½' : ''}
      {'☆'.repeat(empty)}
      <span className="star-rating__num">{rating.toFixed(1)}</span>
    </span>
  )
}

/* ─── Device result card (user-facing) ────────────── */

function DeviceResultCard({ device }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="device-result-card">
      <div className="device-result-card__main">
        <div className="device-result-card__icon">
          <DeviceIcon type={device.image_icon} size={38} />
        </div>
        <div className="device-result-card__info">
          <div className="device-result-card__type-badge">Medical Device</div>
          <div className="device-result-card__name">{device.model_name}</div>
          <div className="device-result-card__brand">{device.brand} · {device.device_name}</div>
          <StarRating rating={device.rating} />
        </div>
        <div className="device-result-card__right">
          <div className="device-result-card__price">₹{device.price.toLocaleString('en-IN')}</div>
          <button
            className="view-details-btn"
            onClick={() => setExpanded(v => !v)}
            aria-expanded={expanded}
          >
            <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{marginRight:3}}>
              {expanded
                ? <path d="M2 8l4-4 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                : <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>}
            </svg>
            {expanded ? 'Hide details' : 'View details'}
          </button>
        </div>
      </div>

      <div className={`device-result-card__detail${expanded ? ' device-result-card__detail--open' : ''}`}>
        <div className="device-result-card__detail-inner">
          {device.uses?.length > 0 && (
            <div className="device-detail-section">
              <div className="device-detail-section__label">
                <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="#bbf7d0"/><path d="M3.5 6l2 2 3-3" stroke="#15803d" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                Uses
              </div>
              <ul className="device-detail-list device-detail-list--green">
                {device.uses.map((u, i) => <li key={i}>{u}</li>)}
              </ul>
            </div>
          )}
          {device.unique_characteristics?.length > 0 && (
            <div className="device-detail-section">
              <div className="device-detail-section__label">
                <svg width="10" height="10" viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M7 1l1.5 3.5L12 5l-2.5 2.5.6 3.5L7 9.5 3.9 11l.6-3.5L2 5l3.5-.5L7 1z" fill="#bfdbfe" stroke="#2457d6" strokeWidth="1" strokeLinejoin="round"/></svg>
                Unique Characteristics
              </div>
              <ul className="device-detail-list device-detail-list--blue">
                {device.unique_characteristics.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Search view ─────────────────────────────────── */

function SearchView({ onResult, onPrescriptionResult, onDeviceSelect }) {
  const [medicine, setMedicine] = useState('')
  const [genericPref, setGenericPref] = useState(true)
  const [loading, setLoading] = useState(false)
  const [suggestionLoading, setSuggestionLoading] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [error, setError] = useState(null)
  const [fdaSearching, setFdaSearching] = useState(false)
  const [activeTab, setActiveTab] = useState('search') // 'search' | 'upload'
  const suppressDropdownRef = useRef(false)
  const [deviceResults, setDeviceResults] = useState([])
  const [deviceSearching, setDeviceSearching] = useState(false)

  async function runRecommendation(medicineName) {
    setLoading(true)
    setError(null)
    setSuggestions([])
    // Also fire device search in parallel
    searchDevices(medicineName)
    try {
      const res = await fetch(`${API_BASE}/api/v1/medicine/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ medicine_name: medicineName, generic_preference: genericPref }),
      })
      if (!res.ok) throw new Error(await res.text())
      onResult(await res.json())
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setLoading(false)
    }
  }

  async function searchDevices(query) {
    if (!query || query.trim().length < 2) { setDeviceResults([]); return }
    setDeviceSearching(true)
    try {
      const res = await fetch(`${API_BASE}/api/v1/devices?q=${encodeURIComponent(query.trim())}`)
      if (!res.ok) { setDeviceResults([]); return }
      const data = await res.json()
      setDeviceResults(data.results || [])
    } catch {
      setDeviceResults([])
    } finally {
      setDeviceSearching(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (medicine.trim()) await runRecommendation(medicine.trim())
  }

  useEffect(() => {
    const query = medicine.trim()
    if (query.length < 2) {
      setSuggestions([]); setFdaSearching(false); setDeviceResults([])
      return undefined
    }
    const controller = new AbortController()
    const tid = window.setTimeout(async () => {
      setSuggestionLoading(true); setFdaSearching(false)
      // ── medicine suggestions ──
      try {
        const res = await fetch(`${API_BASE}/api/v1/medicine/suggest`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query }),
          signal: controller.signal,
        })
        if (!res.ok) { setSuggestions([]); return }
        const data = await res.json()
        setSuggestions(Array.isArray(data.suggestions) ? data.suggestions : [])
        if (data.fda_fallback_used) setFdaSearching(data.suggestions.length === 0)
      } catch (err) {
        if (err.name !== 'AbortError') setSuggestions([])
      } finally {
        setSuggestionLoading(false)
      }
      // ── device search (parallel, non-blocking) ──
      try {
        setDeviceSearching(true)
        const dRes = await fetch(
          `${API_BASE}/api/v1/devices?q=${encodeURIComponent(query)}`,
          { signal: controller.signal }
        )
        if (dRes.ok) {
          const dData = await dRes.json()
          setDeviceResults(dData.results || [])
        } else {
          setDeviceResults([])
        }
      } catch (err) {
        if (err.name !== 'AbortError') setDeviceResults([])
      } finally {
        setDeviceSearching(false)
      }
    }, 300)
    return () => { controller.abort(); window.clearTimeout(tid) }
  }, [medicine])

  async function handleSuggestionClick(s) {
    suppressDropdownRef.current = true
    setSuggestions([])
    setMedicine(s.medicine_name)
    await runRecommendation(s.medicine_name)
  }

  return (
    <div className="search-view">
      <div className="hero">
        <h1 className="hero__brand">gen<span className="hero__brand-r">R</span>x</h1>
        <div className="hero__vendor-nav">
          <a
            href="#vendor"
            className="hero__vendor-link"
            onClick={e => { e.preventDefault(); window.location.hash = '#vendor' }}
          >
            <svg width="12" height="12" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <rect x="2" y="7" width="16" height="11" rx="2" stroke="currentColor" strokeWidth="1.7"/>
              <path d="M6 7V5a4 4 0 018 0v2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/>
            </svg>
            Vendor Dashboard
          </a>
          <a
            href="#vendor-devices"
            className="hero__vendor-link hero__vendor-link--devices"
            onClick={e => { e.preventDefault(); window.location.hash = '#vendor-devices' }}
          >
            <svg width="12" height="12" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <rect x="3" y="3" width="14" height="14" rx="3" fill="none" stroke="currentColor" strokeWidth="1.7"/>
              <path d="M7 10h6M10 7v6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/>
            </svg>
            Device Feedback
          </a>
        </div>
      </div>

      {/* ── Mode tabs ── */}
      <div className="search-tabs surface">
        <button
          type="button"
          className={`search-tab ${activeTab === 'search' ? 'search-tab--active' : ''}`}
          onClick={() => setActiveTab('search')}
          aria-selected={activeTab === 'search'}
        >
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.8"/>
            <path d="M13 13l3.5 3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
          </svg>
          Search Medicine
        </button>
        <button
          type="button"
          className={`search-tab ${activeTab === 'upload' ? 'search-tab--active' : ''}`}
          onClick={() => setActiveTab('upload')}
          aria-selected={activeTab === 'upload'}
        >
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <rect x="3" y="2" width="14" height="16" rx="2.5" stroke="currentColor" strokeWidth="1.6"/>
            <path d="M7 8l3-3 3 3M10 5v7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Upload Prescription
        </button>
      </div>

      {/* ── Search panel ── */}
      {activeTab === 'search' && (
        <>
          <form onSubmit={handleSubmit} className="search-form surface">
            <label className="search-field">
              Medicine name
              <div className="search-input-wrap">
                <input
                  value={medicine}
                  onChange={e => { suppressDropdownRef.current = false; setMedicine(e.target.value) }}
                  placeholder="e.g. Dolo 650, Calpol 500…"
                  autoComplete="off"
                />
                {(suggestionLoading || fdaSearching) && (
                  <span className="search-hint">
                    {fdaSearching ? 'Searching FDA…' : 'Searching…'}
                  </span>
                )}
              </div>
              {fdaSearching && !suggestionLoading && (
                <div className="fda-status">
                  <span className="fda-indicator" /> No local match — searching FDA…
                </div>
              )}
              {!suppressDropdownRef.current && medicine.trim().length >= 2 && (suggestions.length > 0 || deviceResults.length > 0) && (
                <div className="suggestions-dropdown">
                  {suggestions.length > 0 && (
                    <>
                      <div className="suggestions-title">Did you mean</div>
                      <ul className="suggestions-list">
                        {suggestions.map(s => (
                          <li key={s.medicine_name}>
                            <button
                              type="button"
                              className={`suggestion-item ${s.medicine_name.toLowerCase() === medicine.trim().toLowerCase() ? 'suggestion-item--active' : ''}`}
                              onClick={() => handleSuggestionClick(s)}
                            >
                              <span className="suggestion-item__name">{s.medicine_name}</span>
                              <span className="suggestion-item__meta">{s.confidence}% · {s.reason}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}

                  {deviceResults.length > 0 && (
                    <>
                      <div className="suggestions-title suggestions-title--device">
                        <svg width="11" height="11" viewBox="0 0 20 20" fill="none" aria-hidden="true" style={{marginRight:4}}>
                          <rect x="3" y="3" width="14" height="14" rx="3" fill="#dbeafe" stroke="#2563eb" strokeWidth="1.6"/>
                          <path d="M7 10h6M10 7v6" stroke="#2563eb" strokeWidth="1.6" strokeLinecap="round"/>
                        </svg>
                        Medical Devices
                      </div>
                      <ul className="suggestions-list">
                        {deviceResults.map(d => (
                          <li key={d.model_id}>
                            <button
                              type="button"
                              className="suggestion-item suggestion-item--device"
                              onClick={() => {
                                suppressDropdownRef.current = true
                                setSuggestions([])
                                setDeviceResults([])
                                onDeviceSelect(d)
                              }}
                            >
                              <span className="suggestion-item__device-icon">
                                {d.image_icon === 'pacemaker'
                                  ? <svg width="16" height="16" viewBox="0 0 48 48" fill="none"><rect x="10" y="10" width="28" height="28" rx="7" fill="#fce7f3" stroke="#db2777" strokeWidth="1.6"/><path d="M16 24h4l3-6 4 12 3-6h6" stroke="#db2777" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                                  : <svg width="16" height="16" viewBox="0 0 48 48" fill="none"><ellipse cx="24" cy="26" rx="10" ry="7" fill="#dbeafe" stroke="#2563eb" strokeWidth="1.6"/><path d="M14 26 Q12 16 24 14 Q36 16 34 26" stroke="#2563eb" strokeWidth="1.6" fill="none"/><circle cx="24" cy="14" r="2.5" fill="#2563eb"/></svg>
                                }
                              </span>
                              <span className="suggestion-item__device-info">
                                <span className="suggestion-item__name">{d.model_name}</span>
                                <span className="suggestion-item__meta">
                                  <span className="suggestion-item__device-badge">Device</span>
                                  {d.brand} · ₹{d.price.toLocaleString('en-IN')} · ★ {d.rating}
                                </span>
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}

                  <div className="suggestions-footer">
                    Or press <strong>Enter</strong> to search for &ldquo;{medicine.trim()}&rdquo; directly
                  </div>
                </div>
              )}
            </label>

            <label className="row">
              <input type="checkbox" checked={genericPref} onChange={e => setGenericPref(e.target.checked)} />
              <span>Prefer generic</span>
            </label>
            <button type="submit" disabled={loading || !medicine.trim()} className="btn">
              {loading ? 'Searching…' : 'Find Alternatives'}
            </button>
          </form>

          {error && <div className="surface error">{error}</div>}
        </>
      )}

      {/* ── Upload panel ── */}
      {activeTab === 'upload' && (
        <div className="surface rx-upload-panel">
          <PrescriptionUpload onResult={onPrescriptionResult} />
        </div>
      )}
    </div>
  )
}

/* ─── Device Detail View (user-facing) ───────────── */

function DeviceDetailView({ device, onBack }) {
  const full  = Math.floor(device.rating)
  const half  = (device.rating - full) >= 0.5
  const empty = 5 - full - (half ? 1 : 0)
  const stars = '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(empty)

  return (
    <div className="device-detail-view">
      {/* ── Hero ── */}
      <div className="device-detail-hero">
        <button className="device-detail-hero__back" onClick={onBack}>
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back to search
        </button>
        <div className="device-detail-hero__body">
          <div className="device-detail-hero__icon">
            <DeviceIcon type={device.image_icon} size={48} />
          </div>
          <div className="device-detail-hero__info">
            <div className="device-detail-hero__badge">
              <svg width="9" height="9" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <rect x="3" y="3" width="14" height="14" rx="3" fill="none" stroke="currentColor" strokeWidth="2"/>
                <path d="M7 10h6M10 7v6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
              Medical Device
            </div>
            <h1 className="device-detail-hero__name">{device.model_name}</h1>
            <div className="device-detail-hero__brand">{device.brand} · {device.device_name}</div>
            <div className="device-detail-hero__stats">
              <div className="device-detail-hero__rating">
                <span className="device-detail-hero__stars">{stars}</span>
                <span className="device-detail-hero__rating-num">{device.rating.toFixed(1)}</span>
              </div>
              <div className="device-detail-hero__divider" />
              <div className="device-detail-hero__price">
                <span className="device-detail-hero__price-label">MRP</span>
                ₹{device.price.toLocaleString('en-IN')}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Info cards ── */}
      <div className="device-detail-grid">
        <div className="device-detail-card">
          <div className="device-detail-card__heading">
            <svg width="14" height="14" viewBox="0 0 12 12" fill="none" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="#bbf7d0"/><path d="M3.5 6l2 2 3-3" stroke="#15803d" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Uses &amp; Indications
          </div>
          <ul className="device-detail-card__list device-detail-card__list--green">
            {device.uses.map((u, i) => <li key={i}>{u}</li>)}
          </ul>
        </div>

        <div className="device-detail-card">
          <div className="device-detail-card__heading">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M7 1l1.5 3.5L12 5l-2.5 2.5.6 3.5L7 9.5 3.9 11l.6-3.5L2 5l3.5-.5L7 1z" fill="#bfdbfe" stroke="#2457d6" strokeWidth="1" strokeLinejoin="round"/></svg>
            Unique Characteristics
          </div>
          <ul className="device-detail-card__list device-detail-card__list--blue">
            {device.unique_characteristics.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      </div>
    </div>
  )
}

/* ─── Vendor Devices View ─────────────────────────── */

function FeedbackBar({ label, value, max, colorClass }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="feedback-bar">
      <div className="feedback-bar__label">{label}</div>
      <div className="feedback-bar__track">
        <div className={`feedback-bar__fill ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="feedback-bar__count">{value}</div>
    </div>
  )
}

function VendorDeviceCard({ model, deviceName, onViewDetail, analysis, analysing }) {
  const maxFreq = analysis && !analysis.error
    ? Math.max(...analysis.positives.map(p => p.frequency), ...analysis.negatives.map(n => n.frequency), 1)
    : 1

  return (
    <article className="vd-card" onClick={onViewDetail} role="button" tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onViewDetail()}>

      <div className="vd-card__header">
        <div className="vd-card__icon">
          <DeviceIcon type={model.image_icon} size={34} />
        </div>
        <div className="vd-card__meta">
          <div className="vd-card__device-type">{deviceName}</div>
          <div className="vd-card__name">{model.model_name}</div>
          <div className="vd-card__brand">{model.brand}</div>
          <StarRating rating={model.rating} />
        </div>
        <div className="vd-card__price-col">
          <div className="vd-card__price">₹{model.price.toLocaleString('en-IN')}</div>
          <span className="vd-card__view-hint">View details →</span>
        </div>
      </div>

      {analysing && (
        <div className="vd-card__loading" onClick={e => e.stopPropagation()}>
          <span className="vd-spinner" /> Running AI feedback analysis…
        </div>
      )}

      {analysis && !analysis.error && !analysing && (
        <div className="vd-card__analysis" onClick={e => e.stopPropagation()}>
          <div className="vd-analysis-header">
            <span className={`vd-sentiment vd-sentiment--${analysis.overall_sentiment.toLowerCase().replace(/\s+/g, '-')}`}>
              {analysis.overall_sentiment}
            </span>
            <span className="vd-analysis-meta">
              {analysis.total_reviews} reviews · avg <strong>{analysis.avg_rating}</strong>/5
            </span>
          </div>
          <p className="vd-summary">{analysis.summary}</p>
          <div className="vd-feedback-cols">
            <div className="vd-feedback-col">
              <div className="vd-feedback-col__heading vd-feedback-col__heading--pos">
                <svg width="11" height="11" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5" fill="#bbf7d0"/><path d="M3.5 6l2 2 3-3" stroke="#15803d" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                What users love
              </div>
              {analysis.positives.map((p, i) => (
                <FeedbackBar key={i} label={p.point} value={p.frequency} max={maxFreq} colorClass="feedback-bar__fill--pos" />
              ))}
            </div>
            <div className="vd-feedback-col">
              <div className="vd-feedback-col__heading vd-feedback-col__heading--neg">
                <svg width="11" height="11" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5" fill="#fecaca"/><path d="M4 4l4 4M8 4l-4 4" stroke="#dc2626" strokeWidth="1.5" strokeLinecap="round"/></svg>
                Pain points
              </div>
              {analysis.negatives.map((n, i) => (
                <FeedbackBar key={i} label={n.point} value={n.frequency} max={maxFreq} colorClass="feedback-bar__fill--neg" />
              ))}
            </div>
          </div>
          <div className="vd-improvement">
            <svg width="13" height="13" viewBox="0 0 20 20" fill="none"><path d="M10 2l2 6h6l-5 4 2 6-5-4-5 4 2-6-5-4h6z" fill="#fef08a" stroke="#ca8a04" strokeWidth="1.2" strokeLinejoin="round"/></svg>
            <span><strong>Top improvement:</strong> {analysis.top_improvement_area}</span>
          </div>
        </div>
      )}

      {analysis?.error && !analysing && (
        <div className="vd-card__error" onClick={e => e.stopPropagation()}>{analysis.error}</div>
      )}
    </article>
  )
}

function VendorDevicesView({ onBack, onViewDevice }) {
  const [devices, setDevices] = useState([])
  const [loadingList, setLoadingList] = useState(true)
  const [listError, setListError] = useState(null)
  const [analyses, setAnalyses] = useState({})

  // Load all devices then auto-fetch feedback for every model
  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoadingList(true)
      setListError(null)
      try {
        const res = await fetch(`${API_BASE}/api/v1/devices/all`)
        if (!res.ok) throw new Error(await res.text())
        const data = await res.json()
        if (cancelled) return
        setDevices(data)
        setLoadingList(false)

        // Auto-fetch analysis for every model in parallel
        const allModels = data.flatMap(d =>
          d.models.map(m => ({ modelId: m.model_id }))
        )
        allModels.forEach(({ modelId }) => {
          if (cancelled) return
          setAnalyses(prev => ({ ...prev, [modelId]: 'loading' }))
          fetch(`${API_BASE}/api/v1/devices/${modelId}/feedback-analysis`)
            .then(r => r.ok ? r.json() : r.text().then(t => { throw new Error(t) }))
            .then(result => {
              if (!cancelled) setAnalyses(prev => ({ ...prev, [modelId]: result }))
            })
            .catch(err => {
              if (!cancelled) setAnalyses(prev => ({ ...prev, [modelId]: { error: friendlyError(err) } }))
            })
        })
      } catch (err) {
        if (!cancelled) { setListError(friendlyError(err)); setLoadingList(false) }
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const totalModels = devices.reduce((s, d) => s + d.models.length, 0)
  const loadedCount = Object.values(analyses).filter(v => v !== 'loading').length

  return (
    <div className="vd-view">

      {/* ── Hero ── */}
      <div className="vd-hero-bar">
        <div className="vd-hero-bar__left">
          <button className="vd-back-btn" onClick={onBack}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Back to search
          </button>
          <div className="vd-hero-bar__titles">
            <span className="eyebrow">Vendor dashboard</span>
            <h1 className="vd-hero-bar__h1">Device Feedback Analyser</h1>
          </div>
        </div>
        {!loadingList && (
          <div className="vd-hero-bar__right">
            <div className="vd-hero-stat">
              <span className="vd-hero-stat__num">{totalModels}</span>
              <span className="vd-hero-stat__label">Models</span>
            </div>
            <div className="vd-hero-stat__divider" />
            <div className="vd-hero-stat">
              <span className="vd-hero-stat__num">{loadedCount}</span>
              <span className="vd-hero-stat__label">Analysed</span>
            </div>
            {loadedCount < totalModels && (
              <div className="vd-hero-stat__divider" />
            )}
            {loadedCount < totalModels && (
              <div className="vd-hero-stat">
                <span className="vd-spinner vd-spinner--lg" />
                <span className="vd-hero-stat__label">Loading…</span>
              </div>
            )}
          </div>
        )}
      </div>

      {loadingList && (
        <div className="vd-page-loading">
          <span className="vd-spinner vd-spinner--xl" />
          Loading device catalogue…
        </div>
      )}
      {listError && <div className="surface error">{listError}</div>}

      {/* ── Device sections ── */}
      {!loadingList && !listError && devices.map(device => (
        <section key={device.id} className="vd-device-section">
          <div className="vd-device-section__heading">
            <DeviceIcon type={device.category === 'pacemaker' ? 'pacemaker' : 'hearing'} size={20} />
            {device.name}
            <span className="vd-device-section__count">{device.models.length} models</span>
          </div>
          <div className="vd-model-grid">
            {device.models.map(model => {
              const analysis = analyses[model.model_id]
              const analysing = analysis === 'loading'
              const analysisData = analysing ? null : analysis
              return (
                <VendorDeviceCard
                  key={model.model_id}
                  model={model}
                  deviceName={device.name}
                  onViewDetail={() => onViewDevice({ ...model, device_name: device.name })}
                  analysis={analysisData}
                  analysing={analysing}
                />
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}

/* ─── App shell ───────────────────────────────────── */

export default function App() {
  const [result, setResult] = useState(null)
  const [prescriptionResult, setPrescriptionResult] = useState(null)
  const [selectedDevice, setSelectedDevice] = useState(null)
  const [hash, setHash] = useState(() => window.location.hash)
  const [vendorRawDashboard, setVendorRawDashboard] = useState(null)
  const [vendorAiDashboard, setVendorAiDashboard] = useState(null)
  const [vendorLoading, setVendorLoading] = useState(false)
  const [vendorError, setVendorError] = useState(null)
  const [vendorRefreshTick, setVendorRefreshTick] = useState(0)

  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    if (hash !== '#vendor') return undefined
    const controller = new AbortController()
    const loadVendor = async () => {
      setVendorLoading(true)
      setVendorError(null)
      setVendorAiDashboard(null)
      try {
        const rawRes = await fetch(`${API_BASE}/api/v1/vendor/raw`, { signal: controller.signal })
        if (!rawRes.ok) throw new Error(await rawRes.text())
        setVendorRawDashboard(await rawRes.json())
        setVendorLoading(false)
      } catch (err) {
        if (err.name !== 'AbortError') setVendorError(String(err))
        setVendorLoading(false)
        return
      }

      try {
        const aiRes = await fetch(`${API_BASE}/api/v1/vendor/dashboard`, { signal: controller.signal })
        if (!aiRes.ok) throw new Error(await aiRes.text())
        setVendorAiDashboard(await aiRes.json())
      } catch (err) {
        if (err.name !== 'AbortError') {
          setVendorError(`AI recommendations are unavailable right now: ${friendlyError(err)}`)
        }
      }
    }
    loadVendor()
    return () => controller.abort()
  }, [hash, vendorRefreshTick])

  const vendorDashboard = vendorRawDashboard && {
    summary: {
      ...(vendorRawDashboard.summary || {}),
      ...(vendorAiDashboard?.summary || {}),
    },
    medicines: (vendorRawDashboard.medicines || []).map(item => {
      const aiItem = vendorAiDashboard?.medicines?.find(candidate => candidate.id === item.id)
      return aiItem ? { ...item, ...aiItem } : item
    }),
  }

  function handleBackToSearch() {
    setResult(null)
    setPrescriptionResult(null)
    setSelectedDevice(null)
    window.location.hash = ''
    setHash('')
  }

  return (
    <div className="shell">
      {hash === '#vendor-devices' ? (
        <VendorDevicesView
          onBack={() => { window.location.hash = ''; setHash('') }}
          onViewDevice={device => { setSelectedDevice({ ...device, _from: 'vendor-devices' }) }}
        />
      ) : hash === '#vendor' ? (
        <VendorView
          onBackToSearch={() => { window.location.hash = ''; setHash('') }}
          dashboard={vendorDashboard}
          loading={vendorLoading}
          error={vendorError}
          refresh={() => {
            setVendorAiDashboard(null)
            setVendorRefreshTick(v => v + 1)
          }}
        />
      ) : prescriptionResult ? (
        <PrescriptionResults
          data={prescriptionResult}
          onBack={handleBackToSearch}
        />
      ) : result ? (
        <ResultsView result={result} onBack={() => setResult(null)} />
      ) : selectedDevice ? (
        <DeviceDetailView
          device={selectedDevice}
          onBack={() => {
            const from = selectedDevice._from
            setSelectedDevice(null)
            if (from === 'vendor-devices') {
              window.location.hash = '#vendor-devices'
              setHash('#vendor-devices')
            }
          }}
        />
      ) : (
        <SearchView
          onResult={setResult}
          onPrescriptionResult={setPrescriptionResult}
          onDeviceSelect={setSelectedDevice}
        />
      )}
      <footer className="footer">
        <small>genRx · {API_BASE}</small>
      </footer>
    </div>
  )
}

import React, { useState } from 'react'
import PrescriptionSummary from './PrescriptionSummary.jsx'
import PrescriptionSidebar from './PrescriptionSidebar.jsx'

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
          {expanded ? '▲ Show less' : `▾ +${rest.length} more`}
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
            <span className="ins-block__icon">✦</span>
            <span className="ins-block__label">AI Summary</span>
          </div>
          <p className="ins-block__text">{ins.summary}</p>
        </div>
      )}
      {ins.key_uses?.length > 0 && (
        <div className="ins-block ins-block--uses">
          <div className="ins-block__header">
            <span className="ins-block__icon">✓</span>
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
            <span className="ins-block__icon">🛡️</span>
            <span className="ins-block__label">Key Safety Points</span>
          </div>
          <BulletList items={ins.important_safety_points} max={3} colorClass="list--amber" />
        </div>
      )}
      {ins.why_this_generic && (
        <div className="ins-block ins-block--summary" style={{background:'#f0fdf4',borderColor:'#bbf7d0'}}>
          <div className="ins-block__header">
            <span className="ins-block__icon">💡</span>
            <span className="ins-block__label" style={{color:'#15803d'}}>Why this generic?</span>
          </div>
          <p className="ins-block__text">{ins.why_this_generic}</p>
        </div>
      )}
    </div>
  )
}

function AltRowCompact({ alt, refPrice }) {
  const [open, setOpen] = useState(false)
  const pct          = savePct(refPrice, alt.price)
  const priceDisplay = fmt(alt.price)
  const diffDisplay  = fmt(alt.price_difference)
  const ins          = alt.medicine_insights

  return (
    <div className="alt-row">
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
              <span className="spec-tag">{alt.salt_composition}</span>
            )}
            {alt.dosage && <span className="spec-tag">{alt.dosage}</span>}
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
            {alt.same_salt  && <span className="match-badge match-badge--green"><CheckIcon />Same salt</span>}
            {alt.same_dosage && <span className="match-badge match-badge--green"><CheckIcon />Same dosage</span>}
          </div>
          <button className="view-details-btn" onClick={() => setOpen(v => !v)}>
            {open ? 'Hide ▲' : 'Details ›'}
          </button>
        </div>
      </div>
      {open && (
        <div className="alt-row__detail">
          <MedicineInsightsBlock ins={ins} />
        </div>
      )}
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
            <span className="fact-chip"><span className="fact-chip__icon">💊</span>{ref.salt_composition}</span>
          )}
          {ref.dosage_form && (
            <span className="fact-chip"><span className="fact-chip__icon">📋</span>{ref.dosage_form}</span>
          )}
          {ref.dosage && (
            <span className="fact-chip"><span className="fact-chip__icon">⚖️</span>{ref.dosage}</span>
          )}
          {ref.medicine_insights && (
            <button className="view-details-btn" style={{marginLeft:'auto'}}
                    onClick={() => setShowRefInsights(v => !v)}>
              {showRefInsights ? 'Hide info ▲' : 'AI info ›'}
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

        {alts.length === 0 ? (
          <div className="empty-state">No cheaper alternatives found in the database.</div>
        ) : (
          <div className="rx-rec-panel__alt-list">
            {sorted.map(alt => (
              <AltRowCompact key={alt.id} alt={alt} refPrice={ref.price} />
            ))}
          </div>
        )}

        {why && (
          <div className="why-section" style={{marginTop:10}}>
            <div className="why-section__header">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 2L4 6v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V6l-8-4z"
                      fill="#dbe6ff" stroke="#2457d6" strokeWidth="1.5"/>
                <path d="M9 12l2 2 4-4" stroke="#2457d6" strokeWidth="1.8"
                      strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <span>Why these alternatives?</span>
            </div>
            <div className="why-section__body">
              <p className="why-section__text">{why}</p>
            </div>
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
          <span>Prescription Analysis</span>
          <span className="topbar-badge">
            <svg width="11" height="11" viewBox="0 0 16 16" fill="none" style={{marginRight:4}} aria-hidden="true">
              <path d="M8 1L2 4v4c0 3.7 2.56 7.16 6 8 3.44-.84 6-4.3 6-8V4L8 1z"
                    fill="#dcfce7" stroke="#16a34a" strokeWidth="1.2"/>
              <path d="M5.5 8l2 2 3-3" stroke="#16a34a" strokeWidth="1.5"
                    strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            AI-powered OCR prescription analysis
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

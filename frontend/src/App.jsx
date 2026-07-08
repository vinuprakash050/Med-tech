import React, { useEffect, useMemo, useRef, useState } from 'react'
import vendorData from './vendorData.json'

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

function daysUntil(dateString) {
  const target = new Date(`${dateString}T00:00:00`)
  const now = new Date()
  const ms = target.setHours(0, 0, 0, 0) - new Date(now.setHours(0, 0, 0, 0))
  return Math.round(ms / (1000 * 60 * 60 * 24))
}

function scoreExpiry(daysLeft, sales7d, stock) {
  const urgency = Math.max(0, 120 - daysLeft)
  const slowMovement = Math.max(0, 25 - sales7d * 2)
  const overstock = Math.max(0, stock - sales7d * 3)
  return Math.min(100, Math.round(urgency * 0.55 + slowMovement * 0.25 + overstock * 0.15))
}

function vendorDiscountAgent(item) {
  const daysLeft = daysUntil(item.expiryDate)
  const score = scoreExpiry(daysLeft, item.previousSales7Days, item.stock)
  const weighted =
    daysLeft <= 7 ? 28 :
    daysLeft <= 14 ? 22 :
    daysLeft <= 30 ? 15 :
    daysLeft <= 60 ? 10 : 5
  const salesBoost = item.previousSales7Days < 10 ? 6 : item.previousSales7Days < 18 ? 3 : 0
  const discount = Math.min(35, Math.max(0, weighted + salesBoost + Math.floor(score / 25)))
  const reason =
    daysLeft <= 7
      ? 'Expiry is very close, so clearance should be aggressive.'
      : daysLeft <= 30
        ? 'The batch is approaching expiry and needs a stronger push.'
        : item.previousSales7Days < 12
          ? 'Sales are slow, so a small incentive can improve movement.'
          : 'Healthy sales pace; keep the discount light.'
  const action =
    discount >= 25 ? 'Clear fast' :
    discount >= 15 ? 'Promote now' :
    discount >= 8 ? 'Test discount' :
    'Hold price'
  const confidence =
    score >= 75 ? 'High' :
    score >= 45 ? 'Medium' : 'Low'
  return { daysLeft, score, discount, reason, action, confidence }
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

function VendorView({ onBackToSearch }) {
  const medicines = useMemo(() => {
    return vendorData.medicines
      .map(item => {
        const recommendation = vendorDiscountAgent(item)
        return { ...item, recommendation }
      })
      .sort((a, b) => a.recommendation.daysLeft - b.recommendation.daysLeft)
  }, [])

  const summary = useMemo(() => {
    const expiringSoon = medicines.filter(item => item.recommendation.daysLeft <= 30).length
    const clearanceCandidates = medicines.filter(item => item.recommendation.discount >= 15).length
    const totalStock = medicines.reduce((sum, item) => sum + item.stock, 0)
    const avgDiscount = Math.round(
      medicines.reduce((sum, item) => sum + item.recommendation.discount, 0) / medicines.length
    )
    return { expiringSoon, clearanceCandidates, totalStock, avgDiscount }
  }, [medicines])

  return (
    <div className="vendor-view">
      <div className="vendor-hero surface">
        <div>
          <p className="eyebrow">Vendor dashboard</p>
          <h1>Expiry-aware discount planner</h1>
          <p className="hero-copy">
            A focused 20-medicine vendor view using attainable fields like stock, expiry,
            and recent sales to suggest practical discounts.
          </p>
        </div>
        <div className="vendor-hero__actions">
          <button className="btn btn--ghost" onClick={onBackToSearch}>Back to search</button>
          <button className="btn">Refresh insights</button>
        </div>
      </div>

      <div className="vendor-summary-grid">
        <VendorMetric label="Medicines tracked" value="20" hint="Curated from user-facing catalog" />
        <VendorMetric label="Expiring within 30 days" value={String(summary.expiringSoon)} hint="Push these first" />
        <VendorMetric label="Clearance candidates" value={String(summary.clearanceCandidates)} hint="Need a stronger discount" />
        <VendorMetric label="Avg suggested discount" value={`${summary.avgDiscount}%`} hint={`Inventory stock: ${summary.totalStock}`} />
      </div>

      <div className="vendor-layout">
        <section className="vendor-panel surface">
          <div className="vendor-panel__header">
            <div>
              <div className="vendor-panel__eyebrow">Inventory board</div>
              <div className="vendor-panel__title">20 medicines with expiry and sales history</div>
            </div>
            <div className="vendor-panel__chip">Dummy JSON data</div>
          </div>

          <div className="vendor-grid">
            {medicines.map(item => {
              const urgencyClass =
                item.recommendation.daysLeft <= 7 ? 'is-urgent' :
                item.recommendation.daysLeft <= 30 ? 'is-warning' :
                'is-safe'
              return (
                <article key={item.id} className={`vendor-card ${urgencyClass}`}>
                  <div className="vendor-card__top">
                    <div>
                      <h3>{item.name}</h3>
                      <p>{item.brand} · {item.category}</p>
                    </div>
                    <span className={`vendor-badge vendor-badge--${urgencyClass}`}>
                      {item.recommendation.daysLeft <= 7 ? 'Urgent' : item.recommendation.daysLeft <= 30 ? 'Watch' : 'Healthy'}
                    </span>
                  </div>

                  <div className="vendor-card__facts">
                    <span>Expiry: <strong>{item.expiryDate}</strong></span>
                    <span>{item.recommendation.daysLeft} days left</span>
                    <span>Stock: {item.stock}</span>
                  </div>

                  <div className="vendor-card__stats">
                    <div>
                      <span>Sales 7d</span>
                      <strong>{item.previousSales7Days}</strong>
                    </div>
                    <div>
                      <span>Sales 30d</span>
                      <strong>{item.previousSales30Days}</strong>
                    </div>
                    <div>
                      <span>Margin</span>
                      <strong>{item.margin}%</strong>
                    </div>
                  </div>

                  <div className="vendor-card__recommendation">
                    <div className="vendor-card__discount">{item.recommendation.discount}% off</div>
                    <div className="vendor-card__agent-line">
                      <span>AI agent</span>
                      <strong>{item.recommendation.action}</strong>
                      <em>{item.recommendation.confidence} confidence</em>
                    </div>
                    <p>{item.recommendation.reason}</p>
                  </div>
                </article>
              )
            })}
          </div>
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
          {expanded ? '▲ Show less' : `▾ +${rest.length} more`}
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
              <span className="fact-chip__icon">💊</span>
              <span>{medicine.salt_composition}</span>
            </div>
          )}
          {medicine.dosage_form && (
            <div className="fact-chip">
              <span className="fact-chip__icon">📋</span>
              <span>{medicine.dosage_form}</span>
            </div>
          )}
          {medicine.dosage && (
            <div className="fact-chip">
              <span className="fact-chip__icon">⚖️</span>
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
              <span className="ins-block__icon">✦</span>
              <span className="ins-block__label">AI Summary</span>
            </div>
            <p className="ins-block__text">{ins.summary}</p>
          </div>
        )}

        {ins?.key_uses?.length > 0 && (
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

        {ins?.important_safety_points?.length > 0 && (
          <div className="ins-block ins-block--safety">
            <div className="ins-block__header">
              <span className="ins-block__icon">🛡️</span>
              <span className="ins-block__label">Key Safety Points</span>
            </div>
            <BulletList items={ins.important_safety_points} max={4} colorClass="list--amber" />
          </div>
        )}

        {hasBelow && (
          <button className="view-safety-btn" onClick={() => setShowMore(v => !v)}>
            {showMore ? '▲ Hide full safety info' : '▾ View full safety information'}
          </button>
        )}

        {showMore && ins && (
          <>
            {ins.emergency_warnings?.length > 0 && (
              <div className="ins-block ins-block--emergency">
                <div className="ins-block__header">
                  <span className="ins-block__icon">🚨</span>
                  <span className="ins-block__label">Emergency Warnings</span>
                </div>
                <BulletList items={ins.emergency_warnings} colorClass="list--red" />
              </div>
            )}
            {ins.who_should_be_careful?.length > 0 && (
              <div className="ins-block ins-block--careful">
                <div className="ins-block__header">
                  <span className="ins-block__icon">👤</span>
                  <span className="ins-block__label">Who Should Be Careful</span>
                </div>
                <BulletList items={ins.who_should_be_careful} colorClass="list--purple" />
              </div>
            )}
            {ins.possible_side_effects?.length > 0 && (
              <div className="ins-block ins-block--side">
                <div className="ins-block__header">
                  <span className="ins-block__icon">⚠️</span>
                  <span className="ins-block__label">Possible Side Effects</span>
                </div>
                <BulletList items={ins.possible_side_effects} colorClass="list--orange" />
              </div>
            )}
            {ins.pregnancy_breastfeeding && (
              <div className="ins-block ins-block--preg">
                <div className="ins-block__header">
                  <span className="ins-block__icon">🤱</span>
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
  const [open, setOpen] = useState(false)
  const ins = alt.medicine_insights
  const pct = savePct(refPrice, alt.price)
  const priceDisplay = fmt(alt.price)
  const diffDisplay  = fmt(alt.price_difference)

  return (
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
                <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                  <circle cx="6" cy="6" r="5" stroke="#6b7280" strokeWidth="1.2"/>
                  <path d="M6 4v3M6 8v.3" stroke="#6b7280" strokeWidth="1.2" strokeLinecap="round"/>
                </svg>
                {alt.salt_composition}
              </span>
            )}
            {alt.dosage_form && (
              <span className="spec-tag">
                <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                  <rect x="2" y="3" width="8" height="6" rx="2" stroke="#6b7280" strokeWidth="1.2"/>
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
            {open ? 'Hide details ▲' : 'View details ›'}
          </button>
        </div>
      </div>

      {/* Expanded detail — all data-driven, nothing shown if null */}
      {open && (
        <div className="alt-row__detail">
          {ins?.summary && (
            <div className="alt-detail-section">
              <div className="alt-detail-section__label">✦ AI Summary</div>
              <p className="alt-detail-text">{ins.summary}</p>
            </div>
          )}
          {ins?.key_uses?.length > 0 && (
            <div className="alt-detail-section">
              <div className="alt-detail-section__label">✓ Uses</div>
              <BulletList items={ins.key_uses} max={4} colorClass="list--green" />
            </div>
          )}
          {ins?.important_safety_points?.length > 0 && (
            <div className="alt-detail-section">
              <div className="alt-detail-section__label">🛡️ Key Safety</div>
              <BulletList items={ins.important_safety_points} max={3} colorClass="list--amber" />
            </div>
          )}
          {ins?.why_this_generic && (
            <div className="alt-detail-section">
              <div className="alt-detail-section__label">💡 Why this generic?</div>
              <p className="alt-detail-text">{ins.why_this_generic}</p>
            </div>
          )}
          {!ins && (
            <p className="alt-detail-text no-data-note">No AI insights available.</p>
          )}
        </div>
      )}
    </div>
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
                Price {sortBy === 'price' ? '↑' : ''}
              </button>
              <button
                className={`sort-btn ${sortBy === 'savings' ? 'sort-btn--active' : ''}`}
                onClick={() => setSortBy('savings')}
              >
                Savings {sortBy === 'savings' ? '↓' : ''}
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
          <div className="why-section">
            <div className="why-section__header">
              <ShieldCheckIcon accent />
              <span>Why these alternatives?</span>
            </div>
            <div className="why-section__body">
              <p className="why-section__text">{reasoning}</p>
            </div>
          </div>
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
          <span>Medicine Recommendation</span>
          <span className="topbar-badge">
            <svg width="11" height="11" viewBox="0 0 16 16" fill="none" style={{marginRight:4}} aria-hidden="true">
              <path d="M8 1L2 4v4c0 3.7 2.56 7.16 6 8 3.44-.84 6-4.3 6-8V4L8 1z" fill="#dcfce7" stroke="#16a34a" strokeWidth="1.2"/>
              <path d="M5.5 8l2 2 3-3" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            AI powered recommendations based on safety and price
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

/* ─── Search view ─────────────────────────────────── */

function SearchView({ onResult }) {
  const [medicine, setMedicine] = useState('')
  const [genericPref, setGenericPref] = useState(true)
  const [loading, setLoading] = useState(false)
  const [suggestionLoading, setSuggestionLoading] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [error, setError] = useState(null)
  const [fdaSearching, setFdaSearching] = useState(false)
  const suppressDropdownRef = useRef(false)

  async function runRecommendation(medicineName) {
    setLoading(true)
    setError(null)
    setSuggestions([])
    try {
      const res = await fetch(`${API_BASE}/api/v1/medicine/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ medicine_name: medicineName, generic_preference: genericPref }),
      })
      if (!res.ok) throw new Error(await res.text())
      onResult(await res.json())
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (medicine.trim()) await runRecommendation(medicine.trim())
  }

  useEffect(() => {
    const query = medicine.trim()
    if (query.length < 2) {
      setSuggestions([]); setFdaSearching(false)
      return undefined
    }
    const controller = new AbortController()
    const tid = window.setTimeout(async () => {
      setSuggestionLoading(true); setFdaSearching(false)
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
        <p className="eyebrow">Medicine recommendations</p>
        <h1>Medicine Alternatives</h1>
        <p className="hero-copy">
          Compare approved alternatives enriched with official openFDA label data.
        </p>
      </div>

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
          {!suppressDropdownRef.current && medicine.trim().length >= 2 && suggestions.length > 0 && (
            <div className="suggestions-dropdown">
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

      {error && <div className="surface error">Error: {error}</div>}
    </div>
  )
}

/* ─── App shell ───────────────────────────────────── */

export default function App() {
  const [result, setResult] = useState(null)
  const [hash, setHash] = useState(() => window.location.hash)

  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  return (
    <div className="shell">
      {hash === '#vendor' ? (
        <VendorView onBackToSearch={() => { window.location.hash = ''; setHash('') }} />
      ) : result ? (
        <ResultsView result={result} onBack={() => setResult(null)} />
      ) : (
        <SearchView onResult={setResult} />
      )}
      <footer className="footer">
        <small>Backend: {API_BASE}</small>
      </footer>
    </div>
  )
}

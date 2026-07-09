import React from 'react'

/**
 * PrescriptionSummary
 * -------------------
 * Top-bar summary strip for the prescription results view.
 *
 * Props
 * -----
 * summary : PrescriptionSummary object from the API response
 *   { medicines_detected, successfully_matched, failed_matches,
 *     warnings, processing_confidence }
 * patientName : string | null
 * doctor      : string | null
 * date        : string | null
 */
export default function PrescriptionSummary({ summary, patientName, doctor, date }) {
  if (!summary) return null

  const {
    medicines_detected    = 0,
    successfully_matched  = 0,
    failed_matches        = 0,
    warnings              = [],
    processing_confidence = 0,
  } = summary

  const confidenceColor =
    processing_confidence >= 70 ? '#166534' :
    processing_confidence >= 40 ? '#92400e' :
    '#991b1b'

  return (
    <div className="rx-summary surface">
      {/* ── Title row ── */}
      <div className="rx-summary__header">
        <div className="rx-summary__title-block">
          <span className="rx-summary__icon" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <rect x="4" y="3" width="16" height="18" rx="3" fill="#e0eaff" stroke="#3b82f6" strokeWidth="1.4"/>
              <path d="M8 8h8M8 12h5" stroke="#3b82f6" strokeWidth="1.4" strokeLinecap="round"/>
              <path d="M14 15.5l2 2 3-3" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </span>
          <span className="rx-summary__title">Prescription Summary</span>
        </div>

        {/* optional patient / doctor / date metadata */}
        {(patientName || doctor || date) && (
          <div className="rx-summary__meta">
            {patientName && <span className="rx-summary__meta-item">👤 {patientName}</span>}
            {doctor      && <span className="rx-summary__meta-item">🩺 {doctor}</span>}
            {date        && <span className="rx-summary__meta-item">📅 {date}</span>}
          </div>
        )}
      </div>

      {/* ── Metrics row ── */}
      <div className="rx-summary__metrics">
        <div className="rx-summary__metric">
          <span className="rx-summary__metric-value">{medicines_detected}</span>
          <span className="rx-summary__metric-label">Medicines detected</span>
        </div>

        <div className="rx-summary__metric rx-summary__metric--good">
          <span className="rx-summary__metric-value">{successfully_matched}</span>
          <span className="rx-summary__metric-label">Successfully matched</span>
        </div>

        <div className={`rx-summary__metric ${failed_matches > 0 ? 'rx-summary__metric--warn' : 'rx-summary__metric--good'}`}>
          <span className="rx-summary__metric-value">{failed_matches}</span>
          <span className="rx-summary__metric-label">
            {failed_matches > 0 ? 'Failed matches' : 'No failures'}
          </span>
        </div>

        <div className="rx-summary__metric">
          <span
            className="rx-summary__metric-value"
            style={{ color: confidenceColor }}
          >
            {processing_confidence.toFixed(0)}%
          </span>
          <span className="rx-summary__metric-label">Processing confidence</span>
        </div>
      </div>

      {/* ── Warnings ── */}
      {warnings.length > 0 && (
        <div className="rx-summary__warnings">
          {warnings.map((w, i) => (
            <div key={i} className="rx-summary__warning" role="alert">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M8 2L1.5 13h13L8 2z" fill="#fef3c7" stroke="#f59e0b" strokeWidth="1.2"
                      strokeLinejoin="round"/>
                <path d="M8 7v3M8 11.5v.5" stroke="#92400e" strokeWidth="1.2" strokeLinecap="round"/>
              </svg>
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

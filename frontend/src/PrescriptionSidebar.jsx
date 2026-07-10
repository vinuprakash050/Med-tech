import React from 'react'

/**
 * PrescriptionSidebar
 * -------------------
 * Left sidebar listing all medicines extracted from the prescription.
 * Clicking a medicine selects it and shows its recommendation in the main panel.
 *
 * Props
 * -----
 * medicines      : PrescriptionMedicineResult[]
 * selectedIndex  : number
 * onSelect(idx)  : (idx: number) => void
 */
export default function PrescriptionSidebar({ medicines, selectedIndex, onSelect }) {
  if (!medicines?.length) return null

  return (
    <aside className="rx-sidebar surface" aria-label="Prescription medicines list">
      <div className="rx-sidebar__header">
        <span className="rx-sidebar__eyebrow">Prescription</span>
        <span className="rx-sidebar__title">Medicines</span>
      </div>

      <ul className="rx-sidebar__list" role="listbox" aria-label="Select a medicine">
        {medicines.map((med, idx) => {
          const isSelected = idx === selectedIndex
          const isFailed   = !med.matched
          const altCount   = med.recommendation?.recommended_alternatives?.length ?? 0

          return (
            <li
              key={idx}
              className={[
                'rx-sidebar__item',
                isSelected ? 'rx-sidebar__item--active'  : '',
                isFailed   ? 'rx-sidebar__item--failed'  : '',
              ].filter(Boolean).join(' ')}
              role="option"
              aria-selected={isSelected}
              onClick={() => onSelect(idx)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelect(idx)
                }
              }}
              tabIndex={0}
            >
              <span className="rx-sidebar__item-icon" aria-hidden="true">
                {isFailed ? (
                  /* warning triangle */
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                    <path d="M8 2L1.5 13h13L8 2z" fill="#fef3c7" stroke="#f59e0b"
                          strokeWidth="1.2" strokeLinejoin="round"/>
                    <path d="M8 7v3M8 11.5v.5" stroke="#92400e" strokeWidth="1.2" strokeLinecap="round"/>
                  </svg>
                ) : (
                  /* check circle */
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="8" r="6.5" fill="#dcfce7" stroke="#86efac" strokeWidth="1.2"/>
                    <path d="M5 8l2.5 2.5 4-4" stroke="#16a34a" strokeWidth="1.5"
                          strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
              </span>

              <span className="rx-sidebar__item-body">
                <span className="rx-sidebar__item-name">
                  {med.matched_name || med.original_name}
                </span>

                {/* show original name if it was normalised */}
                {med.matched_name && med.matched_name !== med.original_name && (
                  <span className="rx-sidebar__item-original">
                    OCR: {med.original_name}
                  </span>
                )}

                <span className="rx-sidebar__item-meta">
                  {med.dosage    && <span>{med.dosage}</span>}
                  {med.frequency && <span>{med.frequency}</span>}
                  {isFailed && <span className="rx-sidebar__item-fail-note">Not matched</span>}
                </span>

                {/* alternatives count chip — only when matched and alts exist */}
                {!isFailed && altCount > 0 && (
                  <span className="rx-sidebar__item-alts">
                    <svg width="9" height="9" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                      <path d="M2 6h8M7 3l3 3-3 3" stroke="currentColor" strokeWidth="1.4"
                            strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    {altCount} alternative{altCount !== 1 ? 's' : ''}
                  </span>
                )}
              </span>

              {isSelected && (
                <span className="rx-sidebar__item-arrow" aria-hidden="true">
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
                    <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.8"
                          strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </aside>
  )
}

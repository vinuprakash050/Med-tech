import React from 'react'

/**
 * PrescriptionProgress
 * --------------------
 * Shows a step-by-step progress indicator during prescription upload
 * and processing.
 *
 * Props
 * -----
 * step : 'uploading' | 'reading' | 'extracting' | 'matching' | 'done' | 'error'
 */

const STEPS = [
  { key: 'uploading',  label: 'Uploading…'           },
  { key: 'reading',    label: 'Reading prescription…' },
  { key: 'extracting', label: 'Extracting medicines…' },
  { key: 'matching',   label: 'Finding alternatives…' },
  { key: 'done',       label: 'Done'                  },
]

const STEP_INDEX = Object.fromEntries(STEPS.map((s, i) => [s.key, i]))

export default function PrescriptionProgress({ step }) {
  if (!step) return null

  const isError    = step === 'error'
  const currentIdx = isError ? -1 : (STEP_INDEX[step] ?? 0)

  return (
    <div className="rx-progress" role="status" aria-live="polite">
      {STEPS.map((s, idx) => {
        const done    = !isError && idx < currentIdx
        const active  = !isError && idx === currentIdx
        const pending = !isError && idx > currentIdx

        return (
          <div
            key={s.key}
            className={[
              'rx-progress__step',
              done    ? 'rx-progress__step--done'    : '',
              active  ? 'rx-progress__step--active'  : '',
              pending ? 'rx-progress__step--pending' : '',
            ].filter(Boolean).join(' ')}
          >
            <div className="rx-progress__dot">
              {done ? (
                <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                  <circle cx="6" cy="6" r="5" fill="#dcfce7"/>
                  <path d="M3.5 6l2 2 3-3" stroke="#16a34a" strokeWidth="1.5"
                        strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              ) : active ? (
                <span className="rx-progress__spinner" aria-hidden="true" />
              ) : (
                <span className="rx-progress__num" aria-hidden="true">{idx + 1}</span>
              )}
            </div>
            <span className="rx-progress__label">{s.label}</span>
            {idx < STEPS.length - 1 && (
              <span className={`rx-progress__line ${done ? 'rx-progress__line--done' : ''}`}
                    aria-hidden="true" />
            )}
          </div>
        )
      })}

      {isError && (
        <div className="rx-progress__error-note" role="alert">
          Processing failed — see error above.
        </div>
      )}
    </div>
  )
}

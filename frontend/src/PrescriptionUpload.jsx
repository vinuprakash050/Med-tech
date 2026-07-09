import React, { useCallback, useRef, useState } from 'react'
import PrescriptionProgress from './PrescriptionProgress.jsx'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

const ACCEPTED_TYPES  = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
const ACCEPTED_EXTS   = ['.jpg', '.jpeg', '.png', '.webp']
const MAX_MB          = 10

/**
 * PrescriptionUpload
 * ------------------
 * Drag-and-drop / browse prescription image uploader.
 *
 * Props
 * -----
 * onResult(data)  – called with PrescriptionAnalysisResponse on success
 */
export default function PrescriptionUpload({ onResult }) {
  const [dragging,      setDragging]      = useState(false)
  const [selectedFile,  setSelectedFile]  = useState(null)
  const [preview,       setPreview]       = useState(null)
  const [progressStep,  setProgressStep]  = useState(null)
  const [error,         setError]         = useState(null)
  const [genericPref,   setGenericPref]   = useState(true)

  const inputRef = useRef(null)

  // ── File validation ────────────────────────────────────────────────────────

  function validateFile(file) {
    const mime = file.type.toLowerCase()
    const name = file.name.toLowerCase()
    const extOk = ACCEPTED_EXTS.some(e => name.endsWith(e))

    if (name.endsWith('.pdf')) {
      return 'PDF files are not supported yet. Please upload a JPEG or PNG image.'
    }
    if (!ACCEPTED_TYPES.includes(mime) && !extOk) {
      return `Unsupported file type. Please upload a JPEG or PNG image.`
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      return `File is too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is ${MAX_MB} MB.`
    }
    return null
  }

  function pickFile(file) {
    if (!file) return
    const err = validateFile(file)
    if (err) { setError(err); return }

    setError(null)
    setSelectedFile(file)
    setPreview(URL.createObjectURL(file))
    setProgressStep(null)
  }

  // ── Drag-and-drop handlers ─────────────────────────────────────────────────

  const onDragOver = useCallback(e => {
    e.preventDefault()
    setDragging(true)
  }, [])

  const onDragLeave = useCallback(e => {
    e.preventDefault()
    setDragging(false)
  }, [])

  const onDrop = useCallback(e => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) pickFile(file)
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const onFileChange = e => {
    const file = e.target.files?.[0]
    if (file) pickFile(file)
    // reset so same file can be re-selected
    e.target.value = ''
  }

  // ── Upload + analyse ───────────────────────────────────────────────────────

  async function handleAnalyze() {
    if (!selectedFile) return
    setError(null)

    try {
      setProgressStep('uploading')
      await _tick()

      setProgressStep('reading')
      await _tick()

      setProgressStep('extracting')

      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('generic_preference', String(genericPref))

      const res = await fetch(`${API_BASE}/api/v1/prescription/analyze`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(body.detail || res.statusText)
      }

      setProgressStep('matching')
      await _tick()

      const data = await res.json()

      setProgressStep('done')
      await _tick(300)

      onResult(data)
    } catch (err) {
      setProgressStep('error')
      setError(
        err instanceof Error
          ? err.message.replace(/^Error:\s*/, '')
          : String(err)
      )
    }
  }

  function handleClear() {
    setSelectedFile(null)
    setPreview(null)
    setProgressStep(null)
    setError(null)
  }

  const isProcessing = progressStep && progressStep !== 'done' && progressStep !== 'error'

  return (
    <div className="rx-upload">
      {/* ── Drop zone ── */}
      <div
        className={[
          'rx-dropzone',
          dragging       ? 'rx-dropzone--dragging'  : '',
          selectedFile   ? 'rx-dropzone--has-file'  : '',
          isProcessing   ? 'rx-dropzone--processing': '',
        ].filter(Boolean).join(' ')}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => !selectedFile && !isProcessing && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Upload prescription image"
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            if (!selectedFile && !isProcessing) inputRef.current?.click()
          }
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTS.join(',')}
          className="rx-dropzone__input"
          onChange={onFileChange}
          aria-hidden="true"
          tabIndex={-1}
        />

        {selectedFile && preview ? (
          /* ── Preview state ── */
          <div className="rx-dropzone__preview">
            <img
              src={preview}
              alt="Prescription preview"
              className="rx-dropzone__img"
            />
            <div className="rx-dropzone__file-info">
              <span className="rx-dropzone__filename">{selectedFile.name}</span>
              <span className="rx-dropzone__filesize">
                {(selectedFile.size / 1024).toFixed(0)} KB
              </span>
            </div>
            {!isProcessing && (
              <button
                type="button"
                className="rx-dropzone__clear"
                onClick={e => { e.stopPropagation(); handleClear() }}
                aria-label="Remove selected file"
              >
                ✕
              </button>
            )}
          </div>
        ) : (
          /* ── Empty state ── */
          <div className="rx-dropzone__empty">
            <div className="rx-dropzone__icon" aria-hidden="true">
              <svg width="36" height="36" viewBox="0 0 48 48" fill="none">
                <rect x="8" y="6" width="32" height="36" rx="4" fill="#e0eaff" stroke="#3b82f6" strokeWidth="1.5"/>
                <path d="M28 6v10h10" stroke="#3b82f6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M16 26l8-8 8 8" stroke="#3b82f6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M24 18v14" stroke="#3b82f6" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </div>
            <p className="rx-dropzone__title">
              {dragging ? 'Drop prescription here' : 'Drag & drop prescription'}
            </p>
            <p className="rx-dropzone__sub">
              or{' '}
              <span className="rx-dropzone__browse-link">browse files</span>
            </p>
            <p className="rx-dropzone__hint">
              Accepts JPG, PNG · Max {MAX_MB} MB
            </p>
          </div>
        )}
      </div>

      {/* ── Progress indicator ── */}
      {progressStep && (
        <PrescriptionProgress step={progressStep} />
      )}

      {/* ── Error ── */}
      {error && (
        <div className="rx-upload__error" role="alert">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <circle cx="8" cy="8" r="7" fill="#fee2e2" stroke="#f87171" strokeWidth="1.2"/>
            <path d="M8 5v3M8 10v.5" stroke="#dc2626" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          {error}
        </div>
      )}

      {/* ── Controls ── */}
      {selectedFile && !isProcessing && progressStep !== 'done' && (
        <div className="rx-upload__controls">
          <label className="rx-upload__generic-toggle">
            <input
              type="checkbox"
              checked={genericPref}
              onChange={e => setGenericPref(e.target.checked)}
            />
            <span>Prefer generic alternatives</span>
          </label>
          <button
            type="button"
            className="btn rx-upload__analyze-btn"
            onClick={handleAnalyze}
            disabled={isProcessing}
          >
            Analyze Prescription
          </button>
        </div>
      )}
    </div>
  )
}

/** Minimal async tick so React can re-render between state updates. */
function _tick(ms = 80) {
  return new Promise(r => setTimeout(r, ms))
}

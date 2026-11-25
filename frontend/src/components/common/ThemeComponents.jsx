import React from 'react';
import { ArrowRight, Loader2 } from 'lucide-react';

/**
 * Mountain outline logo icon matching reference image design.
 */
export function MountainLogo({ className = 'w-5 h-5', strokeWidth = 1.8 }) {
  return (
    <svg 
      className={className} 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth={strokeWidth} 
      strokeLinecap="round" 
      strokeLinejoin="round"
    >
      <path d="m8 3 4 8 5-5 5 15H2L8 3z" />
    </svg>
  );
}

/**
 * Layered abstract mountain and dune atmospheric artwork background.
 * Uses smooth CSS radial gradients and SVG contours without stock photos.
 */
export function MistyArtworkBackground({ children, className = '', calm = false }) {
  return (
    <div className={`relative min-h-screen w-full overflow-hidden ${calm ? 'calm-background' : 'misty-background'} ${className}`}>
      {!calm && (
        <>
          {/* Subtle blurred mountain silhouette glow */}
          <div 
            className="pointer-events-none absolute inset-0 z-0 opacity-40"
            style={{
              background: `
                radial-gradient(ellipse 65% 45% at 55% 40%, rgba(200, 220, 215, 0.22) 0%, transparent 60%),
                radial-gradient(ellipse 85% 50% at 30% 65%, rgba(18, 38, 42, 0.75) 0%, transparent 70%)
              `
            }}
          />

          {/* Abstract SVG mountain silhouette contour at lower section */}
          <svg 
            className="pointer-events-none absolute -bottom-10 left-0 right-0 w-full z-0 opacity-20"
            viewBox="0 0 1440 320" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
            preserveAspectRatio="none"
          >
            <path 
              d="M0,192L80,186.7C160,181,320,171,480,186.7C640,203,800,245,960,240C1120,235,1280,181,1360,154.7L1440,128L1440,320L1360,320C1280,320,1120,320,960,320C800,320,640,320,480,320C320,320,160,320,80,320L0,320Z" 
              fill="#122326"
            />
          </svg>

          {/* Corner subtle dot grid accents */}
          <div className="pointer-events-none absolute top-6 right-8 w-32 h-32 dot-grid opacity-30 z-0" />
          <div className="pointer-events-none absolute bottom-8 left-8 w-40 h-40 dot-grid opacity-25 z-0" />
        </>
      )}

      {/* Main children content */}
      <div className="relative z-10 w-full min-h-screen">
        {children}
      </div>
    </div>
  );
}

/**
 * Curved section divider (SVG wave/arc) between major sections.
 */
export function CurvedDivider({ flip = false, className = '' }) {
  return (
    <div className={`w-full overflow-hidden leading-none pointer-events-none select-none my-6 ${className}`}>
      <svg 
        className={`w-full h-8 sm:h-12 text-white/[0.06] ${flip ? 'rotate-180' : ''}`} 
        viewBox="0 0 1200 120" 
        preserveAspectRatio="none"
      >
        <path 
          d="M0,0 C300,90 900,90 1200,0 L1200,120 L0,120 Z" 
          fill="currentColor"
        />
      </svg>
    </div>
  );
}

/**
 * Frosted Glass Card container.
 */
export function GlassCard({ 
  children, 
  className = '', 
  hover = true, 
  dark = false,
  style = {},
  ...props 
}) {
  return (
    <div 
      className={`
        ${dark ? 'glass-dark-card' : 'glass-card'} 
        ${hover ? 'glass-card-hover' : ''} 
        ${className}
      `}
      style={style}
      {...props}
    >
      {children}
    </div>
  );
}

/**
 * Primary action button: Pale cream/sage fill with small dark circle arrow icon.
 */
export function CreamButton({ 
  children, 
  onClick, 
  loading = false, 
  disabled = false, 
  icon = true,
  className = '',
  type = 'button',
  ...props 
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`pill-cream disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
      {...props}
    >
      <span>{children}</span>
      {loading ? (
        <span className="pill-arrow-icon">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        </span>
      ) : icon ? (
        <span className="pill-arrow-icon" aria-hidden="true">
          <ArrowRight className="w-3.5 h-3.5" />
        </span>
      ) : null}
    </button>
  );
}

/**
 * Secondary pill button with frosted glass effect.
 */
export function GlassPill({ 
  children, 
  onClick, 
  active = false, 
  className = '', 
  ...props 
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        pill-glass 
        ${active ? 'bg-white/20 border-white/40 text-white' : ''} 
        ${className}
      `}
      {...props}
    >
      {children}
    </button>
  );
}

/**
 * Step Card with giant faint outline number (01, 02, etc.) in the background.
 */
export function StepCard({ stepNumber, title, description, className = '' }) {
  const formattedNum = String(stepNumber).padStart(2, '0');
  return (
    <div className={`step-card ${className}`}>
      <div className="step-card-num" aria-hidden="true">
        {formattedNum}
      </div>
      <div className="relative z-10 pt-2">
        <h4 className="text-base sm:text-lg font-medium text-[#f3f6f2] mb-1">
          {title}
        </h4>
        <p className="text-xs sm:text-sm text-[#c9d6d3] leading-relaxed max-w-[180px]">
          {description}
        </p>
      </div>
    </div>
  );
}

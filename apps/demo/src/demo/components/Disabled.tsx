import type { ReactNode } from 'react';

interface Props {
  children: ReactNode;
  message?: string;
  /** Which side the tooltip opens toward. Controls placed near the top of
   * the page (the header) need "down" — "up" pushes the tooltip above the
   * viewport/a clipping ancestor and it never becomes visible. */
  direction?: 'up' | 'down';
}

/** Wraps a control that exists for visual parity with the dev dashboard but
 * is inert in the public demo — hovering explains why. */
export function Disabled({
  children,
  message = 'Read-only demo — this control is disabled',
  direction = 'up',
}: Props) {
  const sideClass = direction === 'up' ? 'bottom-full mb-1' : 'top-full mt-1';
  return (
    <span className="relative inline-block group">
      <span className="opacity-50 cursor-not-allowed pointer-events-none">{children}</span>
      <span
        className={`pointer-events-none absolute left-1/2 -translate-x-1/2 ${sideClass} whitespace-nowrap rounded bg-gray-900 text-white text-xs px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity z-50`}
      >
        {message}
      </span>
    </span>
  );
}

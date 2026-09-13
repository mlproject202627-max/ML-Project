export function Logomark({ size = 30 }: { size?: number }) {
  return (
    <span
      className="relative grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 32 32" width={size} height={size}>
        <defs>
          <linearGradient id="logoGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="55%" stopColor="#d4d4d4" />
            <stop offset="100%" stopColor="#a3a3a3" />
          </linearGradient>
        </defs>
        <path
          d="M16 2.6 5.2 6.9v8.4c0 6.4 4.4 11.9 10.8 14.1 6.4-2.2 10.8-7.7 10.8-14.1V6.9L16 2.6Z"
          fill="url(#logoGrad)"
          fillOpacity="0.12"
          stroke="url(#logoGrad)"
          strokeWidth="1.4"
        />
        <path
          d="M10.4 16.2h2.6l1.8-3.4 2.2 6.6 2-4.3 1.1 1.6h2.5"
          fill="none"
          stroke="url(#logoGrad)"
          strokeWidth="1.9"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  )
}

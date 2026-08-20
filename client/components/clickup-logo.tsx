export function ClickUpMark({ className }: { className?: string }) {
  // Simplified ClickUp brand symbol (two chevrons) in accent purple.
  return (
    <svg
      viewBox="0 0 100 100"
      className={className}
      aria-hidden="true"
      fill="none"
    >
      <path
        d="M6 74.2 24.6 60c6.6 8.6 13.7 12.6 22.3 12.6 8.5 0 15.4-3.9 21.7-12.5L87.4 74.5C78.3 87 66.4 93.6 47 93.6 27.6 93.6 15.6 86.9 6 74.2Z"
        fill="#7b68ee"
      />
      <path
        d="M47 24.5 23.3 44.9 13.1 33.1 47 3.8l34 29.3-10.2 11.8L47 24.5Z"
        fill="#7b68ee"
      />
    </svg>
  )
}

export function ClickUpWordmark({ className }: { className?: string }) {
  return (
    <span className={className}>
      <span className="font-semibold tracking-tight text-foreground">Click</span>
      <span className="font-semibold tracking-tight text-primary">Up</span>
    </span>
  )
}

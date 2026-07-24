import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { Icon, type IconName } from './Icon'

export function StatusBadge({
  label,
  tone = 'neutral',
}: {
  readonly label: string
  readonly tone?: 'positive' | 'warning' | 'danger' | 'neutral' | 'info'
}) {
  return (
    <span className={`status-badge status-badge--${tone}`}>
      <span className="status-badge__dot" aria-hidden="true" />
      {label}
    </span>
  )
}

export function Button({
  children,
  icon,
  variant = 'primary',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  readonly icon?: IconName
  readonly variant?: 'primary' | 'secondary' | 'quiet' | 'danger'
}) {
  return (
    <button className={`button button--${variant}`} {...props}>
      {icon ? <Icon name={icon} /> : null}
      {children}
    </button>
  )
}

export function Surface({
  children,
  className = '',
}: {
  readonly children: ReactNode
  readonly className?: string
}) {
  return <section className={`surface ${className}`.trim()}>{children}</section>
}

export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  readonly eyebrow: string
  readonly title: string
  readonly description: string
  readonly action?: ReactNode
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-heading__description">{description}</p>
      </div>
      {action ? <div className="page-heading__action">{action}</div> : null}
    </header>
  )
}

import { PropsWithChildren } from 'react';

type BadgeTone = 'success' | 'warning' | 'error' | 'info';

type BadgeProps = PropsWithChildren<{
  tone: BadgeTone;
  className?: string;
}>;

export function Badge({ tone, className = '', children }: BadgeProps) {
  const classes = ['ui-badge', tone];
  if (className) {
    classes.push(className);
  }
  return <span className={classes.join(' ')}>{children}</span>;
}

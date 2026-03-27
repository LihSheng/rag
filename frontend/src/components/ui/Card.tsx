import { PropsWithChildren } from 'react';

type CardProps = PropsWithChildren<{
  className?: string;
  flat?: boolean;
  tight?: boolean;
}>;

export function Card({ children, className = '', flat = false, tight = false }: CardProps) {
  const classes = ['ui-card'];

  if (flat) {
    classes.push('ui-card--flat');
  }

  if (tight) {
    classes.push('ui-card--tight');
  }

  if (className) {
    classes.push(className);
  }

  return <section className={classes.join(' ')}>{children}</section>;
}

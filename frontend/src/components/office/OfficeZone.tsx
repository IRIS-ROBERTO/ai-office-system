import type { CSSProperties, ReactNode } from 'react';

interface OfficeZoneProps {
  title: string;
  subtitle: string;
  accent: string;
  badge?: string;
  children: ReactNode;
}

export function OfficeZone({ title, subtitle, accent, badge, children }: OfficeZoneProps) {
  return (
    <section className="zone-shell panel-surface" style={{ ['--zone-accent' as any]: accent } as CSSProperties}>
      <div className="zone-shell__header">
        <div>
          <div className="eyebrow">{title}</div>
          <p className="zone-shell__subtitle">{subtitle}</p>
        </div>
        {badge ? <span className="zone-badge">{badge}</span> : null}
      </div>
      <div className="zone-shell__body">{children}</div>
    </section>
  );
}

export default OfficeZone;

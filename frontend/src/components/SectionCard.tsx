import { PropsWithChildren } from "react";

type Props = PropsWithChildren<{
  title: string;
  subtitle?: string;
}>;

export default function SectionCard({ title, subtitle, children }: Props) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

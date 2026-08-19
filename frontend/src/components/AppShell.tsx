import React from "react";
import type { ReactNode } from "react";

export interface AppShellProps {
  header?: ReactNode;
  controls?: ReactNode;
  scenarios?: ReactNode;
  map: ReactNode;
  comparison?: ReactNode;
  timeline?: ReactNode;
  children?: ReactNode;
}

export function AppShell({
  header,
  controls,
  scenarios,
  map,
  comparison,
  timeline,
  children,
}: AppShellProps) {
  return (
    <main className="app-shell">
      {header ? <header className="app-shell__header">{header}</header> : null}
      <div className="app-shell__workspace">
        <aside aria-label="Configuração da operação" className="app-shell__left">
          {controls}
          {scenarios}
        </aside>
        <section aria-label="Mapa operacional" className="app-shell__map">
          {map}
        </section>
        <aside aria-label="Comparação de desempenho" className="app-shell__right">
          {comparison}
        </aside>
      </div>
      <section aria-label="Linha do tempo" className="app-shell__timeline">
        {timeline}
      </section>
      <section aria-labelledby="flow-explainer-title" className="app-shell__explainer">
        <h2 id="flow-explainer-title">Como a decisão é formada</h2>
        <ol>
          <li>Contagens de câmeras</li>
          <li>Fluxo no grafo viário</li>
          <li>Densidade H3</li>
          <li>Previsão de chamados</li>
          <li>Alocação de ambulâncias</li>
        </ol>
      </section>
      {children}
      <style>{`
        .app-shell { min-height: 100dvh; display: grid; grid-template-rows: auto minmax(0, 1fr) auto auto; gap: 12px; }
        .app-shell__workspace { min-height: 0; display: grid; grid-template-columns: minmax(280px, 22vw) minmax(0, 1fr) minmax(310px, 25vw); gap: 12px; }
        .app-shell__left, .app-shell__right { min-height: 0; overflow: auto; }
        .app-shell__map { min-width: 0; min-height: 420px; position: relative; }
        .app-shell__explainer ol { display: flex; flex-wrap: wrap; gap: 8px 20px; margin: 0; padding: 0; list-style: none; }
        .app-shell__explainer li + li::before { content: "→"; margin-right: 20px; color: #78e6c4; }
        @media (max-width: 960px) {
          .app-shell__workspace { grid-template-columns: minmax(220px, 32vw) minmax(0, 1fr); }
          .app-shell__right { grid-column: 1 / -1; }
        }
        @media (max-width: 680px) {
          .app-shell__workspace { grid-template-columns: 1fr; }
          .app-shell__right { grid-column: auto; }
          .app-shell__map { min-height: 55dvh; grid-row: 1; }
        }
      `}</style>
    </main>
  );
}

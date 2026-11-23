import { forwardRef } from 'react';
import logoSrc from '../assets/logo.png';

/**
 * A crafted, static replica of the real dashboard for the landing page.
 * Example data from the Bento product overview — not a live account.
 */
export const DashboardPreview = forwardRef<HTMLDivElement, { className?: string }>(function DashboardPreview({ className }, ref) {
  const trend = [96, 95, 95, 93, 94, 92, 90, 91, 89, 88, 90, 91, 92, 93];
  const path = trend
    .map((v, i) => `${i ? 'L' : 'M'}${(i / (trend.length - 1)) * 100} ${((100 - v) / 14) * 30}`)
    .join('');

  return (
    <div ref={ref} className={`dp ${className ?? ''}`} role="img" aria-label="Preview of the Bento dashboard with example projects">
      <div className="dp-bar">
        <span className="dp-brand"><img src={logoSrc} alt="Bento" /></span>
        <span className="dp-live"><b /> Monitoring live</span>
      </div>
      <div className="dp-body">
        <div className="dp-hero">
          <div>
            <p className="dp-eyebrow">Monday, 3 November</p>
            <p className="dp-title">Good morning, <b>Maya.</b></p>
            <div className="dp-pickle">
              <p className="dp-pickle-label">Pickle · daily brief</p>
              <p>Your portfolio looks healthy today. Pickle reviewed 7 open issues and picked the three that matter most. The biggest risk is a critical vulnerability in Proxy.</p>
            </div>
          </div>
          <div className="dp-health">
            <p className="dp-label">Portfolio health</p>
            <p className="dp-num">93<span>/100</span></p>
            <svg viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true">
              <path d={`${path}L100 30L0 30Z`} fill="rgba(200,98,26,.12)" />
              <path d={path} fill="none" stroke="#c8621a" strokeWidth="2" vectorEffect="non-scaling-stroke" />
            </svg>
            <div className="dp-stats"><span>Projects <b>4</b></span><span>Attention <b>2</b></span><span>Incidents <b className="crit">0</b></span></div>
          </div>
        </div>
        <div className="dp-cols">
          <div>
            <p className="dp-h">What deserves your attention today</p>
            {[
              ['01', 'Dependency vulnerability', 'Proxy · Critical · ~20 min', true],
              ['02', 'Accessibility score dropped 21%', 'SkillAble · High · ~45 min', false],
              ['03', 'Needs dependency updates', 'GetMyHelp · Medium · ~15 min', false],
            ].map(([n, t, m, risk]) => (
              <div className="dp-task" key={n as string}>
                <span className="dp-n">{n}</span>
                <div>
                  {risk && <span className="dp-flag">Biggest risk</span>}
                  <p className="dp-t">{t}</p>
                  <p className="dp-m">{m}</p>
                </div>
              </div>
            ))}
          </div>
          <div>
            <p className="dp-h">Projects</p>
            {[
              ['SkillAble', 74, 'warn'],
              ['Proxy', 81, 'ok'],
              ['GetMyHelp', 88, 'ok'],
              ['Footnote', 97, 'ok'],
            ].map(([name, score, s]) => (
              <div className="dp-proj" key={name as string}>
                <span>{name}</span>
                <span className="dp-track"><span className={`dp-fill ${s}`} style={{ width: `${score}%` }} /></span>
                <b>{score}</b>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
});

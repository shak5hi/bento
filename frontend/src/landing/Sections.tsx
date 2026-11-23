import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { auth } from '../lib/api';
import { useReveal } from './useReveal';
import logoSrc from '../assets/logo.png';

const primaryHref = () => (auth.token ? '/dashboard' : '/login');

/* ───────────────────────── nav ───────────────────────── */

export function LandingNav() {
  const [hidden, setHidden] = useState(false);
  const [solid, setSolid] = useState(false);

  useEffect(() => {
    let last = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      setSolid(y > 24);
      setHidden(y > 160 && y > last + 4 ? true : y < last - 4 ? false : (h) => h);
      last = y;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const go = (id: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <header className={`lnav ${hidden ? 'is-hidden' : ''} ${solid ? 'is-solid' : ''}`}>
      <a href="#top" className="lnav-brand" onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>
        <img src={logoSrc} alt="Bento" />
      </a>
      <nav className="lnav-links" aria-label="Sections">
        <a href="#problem" onClick={go('problem')}>Why Bento</a>
        <a href="#how" onClick={go('how')}>How it works</a>
        <a href="#pickle" onClick={go('pickle')}>Pickle</a>
        <a href="#score" onClick={go('score')}>Health score</a>
      </nav>
      <div className="lnav-actions">
        {!auth.token && <Link to="/login" className="lnav-signin">Sign in</Link>}
        <Link to={primaryHref()} className="lnav-cta">{auth.token ? 'Open dashboard' : 'Get started'}</Link>
      </div>
    </header>
  );
}

/* ───────────────────────── 01 · the problem ───────────────────────── */

const TOOLS = ['GitHub', 'Vercel', 'Railway', 'Supabase', 'Sentry', 'Docker', 'GitHub Actions', 'Cloudflare', 'Grafana', 'npm', 'Dependabot', 'Lighthouse'];

const DECAY = [
  ['Dependencies became outdated', 'portfolio-site', '9 months'],
  ['Certificate expires in 6 days', 'client-dashboard', 'soon'],
  ['Deploys failing quietly', 'hackathon-app', '3 weeks'],
  ['API 40% slower than last month', 'saas-api', '1 month'],
  ['Build broken on main', 'mobile-app', '12 days'],
  ['Tests stopped running', 'admin-panel', '2 months'],
];

function Problem() {
  const ref = useReveal<HTMLElement>();
  return (
    <section id="problem" className="lsec lsec-paper" ref={ref}>
      <div className="lwrap lgrid">
        <div>
          <p className="leyebrow reveal">01 · The problem</p>
          <h2 className="lh2 reveal">Software doesn't break. <b>It quietly decays.</b></h2>
          <p className="llede reveal">
            Modern developers rarely build just one thing. A portfolio, a hackathon project, three client apps, a SaaS on the side — each
            spread across its own set of tools. Checking every one of them by hand stops being possible long before anyone notices.
          </p>
          <dl className="personas reveal">
            <div><dt>A student</dt><dd>Portfolio, coursework, internship project, a startup idea — all at once.</dd></div>
            <div><dt>A freelancer</dt><dd>Up to twelve client projects, each with its own deadlines and infrastructure.</dd></div>
            <div><dt>An indie hacker</dt><dd>Eight products, each needing servers and monitoring nobody else is watching.</dd></div>
          </dl>
        </div>

        <div className="decay reveal" aria-label="Example of what decays unnoticed">
          <p className="decay-head">
            <span>What nobody noticed</span>
            <span className="muted">6 projects</span>
          </p>
          <ul>
            {DECAY.map(([what, project, when], i) => (
              <li key={what} style={{ transitionDelay: `${i * 70}ms` }}>
                <span className="decay-dot" />
                <span className="decay-what">{what}<em>{project}</em></span>
                <span className="decay-when">{when}</span>
              </li>
            ))}
          </ul>
          <p className="decay-foot">By the time you open the old portfolio again, it's already broken.</p>
        </div>
      </div>

      <div className="tools" aria-label="Tools a typical project spans">
        <div className="tools-track">
          {[...TOOLS, ...TOOLS].map((t, i) => (
            <span key={i}>{t}</span>
          ))}
        </div>
      </div>
      <p className="tools-caption lwrap">Twelve dashboards. One of you.</p>
    </section>
  );
}

/* ───────────────────────── 02 · how it works ───────────────────────── */

function HowItWorks() {
  const ref = useReveal<HTMLElement>();
  const steps = [
    ['Connect your project', 'GitHub, your deployment platform, your endpoints. Connect once — nothing to rebuild or migrate.'],
    ['Bento builds a health profile', 'It probes every minute, scans the code on every push and learns what normal looks like for each project.'],
    ['You get priorities, not noise', 'Instead of a wall of charts, a short ranked list of what actually matters today.'],
  ];
  return (
    <section id="how" className="lsec lsec-paper2" ref={ref}>
      <div className="lwrap lgrid">
        <div>
          <p className="leyebrow reveal">02 · How it works</p>
          <h2 className="lh2 reveal">Three steps, and the <b>complexity disappears.</b></h2>
          <ol className="lsteps">
            {steps.map(([t, d], i) => (
              <li key={t} className="reveal" style={{ transitionDelay: `${i * 90}ms` }}>
                <span>{String(i + 1).padStart(2, '0')}</span>
                <div><h3>{t}</h3><p>{d}</p></div>
              </li>
            ))}
          </ol>
        </div>

        <div className="reveal">
          <div className="alert-panel">
            <div className="alert-head">
              <div>
                <p className="lab">Project</p>
                <p className="alert-name">Proxy</p>
              </div>
              <span className="pill pill-ok">Deployment healthy</span>
            </div>
            <div className="alert-row"><span>Prompt costs increased</span><b className="t-warn">+18%</b></div>
            <div className="alert-row"><span>Dependency vulnerability found</span><b className="t-crit">Critical</b></div>
            <div className="alert-row"><span>Worker queue behaviour</span><b className="t-warn">Occasionally stalls</b></div>
          </div>
          <div className="fix-note">
            <p className="lab lab-accent">Suggested fix</p>
            <p>Update the vulnerable package, then move retries into the queue worker.</p>
            <p className="fix-time">Estimated time · 20 minutes</p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────── 03 · Pickle ───────────────────────── */

const QUOTES = [
  'This API has become slower over the past month.',
  'This dependency has been vulnerable for six weeks.',
  'This project has production code but no automated tests.',
  "You haven't updated this repository in nine months.",
  'This README no longer matches the implementation.',
  'This project would benefit from Redis caching.',
];

function Pickle() {
  const ref = useReveal<HTMLElement>();
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setI((n) => (n + 1) % QUOTES.length), 3200);
    return () => window.clearInterval(id);
  }, []);
  return (
    <section id="pickle" className="lsec lsec-dark" ref={ref}>
      <div className="lwrap">
        <p className="leyebrow leyebrow-dark reveal">03 · Meet Pickle</p>
        <h2 className="lh2 lh2-dark reveal">AI is not the product. <b>AI is the engineering assistant.</b></h2>

        <div className="pickle-grid">
          <div className="reveal">
            <p className="pickle-intro">
              Pickle reviews every connected project in the background and tells you what it found in plain language — like a calm,
              experienced teammate who already read all the logs.
            </p>
            <div className="contrast">
              <div><p className="lab">Most tools answer</p><p className="contrast-q">“What is happening?”</p></div>
              <div><p className="lab lab-accent">Bento answers</p><p className="contrast-q contrast-a">“What should I do next?”</p></div>
            </div>
          </div>

          <div className="reveal">
            <div className="speech" aria-live="polite">
              <p className="lab lab-accent">Pickle</p>
              <p key={i} className="speech-text">“{QUOTES[i]}”</p>
              <div className="speech-dots" aria-hidden="true">
                {QUOTES.map((_, n) => <span key={n} className={n === i ? 'on' : ''} />)}
              </div>
            </div>
            <div className="flow">
              {['Explains', 'Prioritises', 'Suggests', 'Never overwhelms'].map((s, n) => (
                <span key={s} className="flow-node" style={{ transitionDelay: `${n * 80}ms` }}>{s}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────── 04 · health score ───────────────────────── */

const SCORES: [string, number][] = [
  ['Performance', 94], ['Security', 88], ['Testing', 72], ['Accessibility', 90],
  ['Documentation', 95], ['Deployment', 100], ['Dependencies', 81], ['Architecture', 89],
];

function HealthScore() {
  const ref = useReveal<HTMLElement>();
  return (
    <section id="score" className="lsec lsec-paper" ref={ref}>
      <div className="lwrap lgrid">
        <div>
          <p className="leyebrow reveal">04 · Engineering Health Score</p>
          <h2 className="lh2 reveal">Not stars. Not commits. <b>Real quality.</b></h2>
          <p className="llede reveal">
            Every project gets a living score that changes daily, just like the project itself. A star count tells you how popular a
            project looks. A health score tells you whether it breaks in production next month.
          </p>
          <div className="says reveal">
            <div><p className="lab">A typical tool says</p><p>“Five outdated packages.”</p></div>
            <div><p className="lab lab-accent">Pickle says</p><p>“Your portfolio health dropped from 96 to 82 over four months because these projects haven't been maintained.”</p></div>
          </div>
        </div>

        <div className="score-card reveal">
          <div className="score-top">
            <div><p className="lab">Overall health</p><p className="score-big">92</p></div>
            <span className="pill pill-ok">Stable</span>
          </div>
          <ul className="score-bars">
            {SCORES.map(([label, v], i) => (
              <li key={label}>
                <span>{label}</span>
                <span className="sb-track"><span className="sb-fill" style={{ ['--w' as string]: `${v}%`, transitionDelay: `${150 + i * 60}ms` }} /></span>
                <b>{v}</b>
              </li>
            ))}
          </ul>
          <p className="score-note">Example project</p>
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────── 05 · weekly review + vision ───────────────────────── */

const REPORT: [string, string][] = [
  ['Portfolio health', '93 → 95 this week'],
  ['Projects improved', 'GetMyHelp, Footnote'],
  ['Projects at risk', 'SkillAble — accessibility trending down'],
  ['Security', '2 vulnerabilities found, 3 resolved'],
  ['Failed deployments', 'None'],
  ['Suggested focus', 'Finish the SkillAble ARIA fixes'],
];

function Weekly() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="lsec lsec-paper2" ref={ref}>
      <div className="lwrap lgrid lgrid-flip">
        <div className="report reveal">
          <div className="report-head">
            <p className="lab">Engineering report</p>
            <p className="report-date">Monday, 3 November</p>
          </div>
          <dl>
            {REPORT.map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
        </div>
        <div>
          <p className="leyebrow reveal">05 · The weekly review</p>
          <h2 className="lh2 reveal">Find out on Monday morning, <b>not from a user.</b></h2>
          <p className="llede reveal">
            Every Monday Bento writes an engineering report: what improved, what's at risk, what broke and what to focus on. Over time it
            becomes your engineering journal.
          </p>
          <div className="vision reveal">
            <p className="lab">Where Bento is going</p>
            <div className="vision-flow">
              <span>Monitoring</span><i>→</i><span>Recommendations</span><i>→</i><span>Automation</span>
            </div>
            <p className="vision-rule">The repetitive work disappears. The decision-making never does.</p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────── closing CTA ───────────────────────── */

function Closing() {
  const ref = useReveal<HTMLElement>();
  return (
    <section className="lsec lsec-brand" ref={ref}>
      <div className="lwrap closing">
        <h2 className="closing-h reveal">Open one place. <b>Know exactly what to do next.</b></h2>
        <div className="closing-actions reveal">
          <Link to={primaryHref()} className="closing-cta">{auth.token ? 'Open your dashboard' : 'Get started'}</Link>
          {!auth.token && <Link to="/login" className="closing-link">I already have an account</Link>}
        </div>
      </div>
    </section>
  );
}

export function LandingSections() {
  return (
    <main className="lsections">
      <Problem />
      <HowItWorks />
      <Pickle />
      <HealthScore />
      <Weekly />
      <Closing />
    </main>
  );
}

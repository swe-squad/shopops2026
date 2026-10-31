import { BrowserIcon } from './browser-icon'
import { defaultShopPath } from './app-route'

export function LandingPage({ authenticated }: { authenticated: boolean }) {
  const href = authenticated ? defaultShopPath : '/login'
  const label = authenticated ? 'Open workspace' : 'Explore the workspace'
  return <div className="landing">
    <section className="landing-hero" aria-labelledby="hero-title">
      <div className="hero-copy">
        <span className="eyebrow"><span className="eyebrow-line" />YOUR SHOP, ON TRACK</span>
        <h1 id="hero-title">Clarity in<br /><em>the chaos.</em></h1>
        <p>A busy shop. A clearer perspective.<br />Capture issues, keep the details close, and choose the next step for your shop.</p>
        <a className="primary-button hero-cta" href={href}>{label}<BrowserIcon name="arrow" /></a>
        <span className="hero-note">Get started with your workspace token.</span>
      </div>
      <figure className="workspace-illustration">
        <div className="illustration-orbit" aria-hidden="true" />
        <div className="illustration-window" aria-hidden="true">
          <div className="illustration-top"><span className="illustration-dots"><i /><i /><i /></span><span>Seller workspace</span><BrowserIcon name="lock" /></div>
          <div className="illustration-body">
            <div className="illustration-greeting"><img src="/brand/mark-primary.svg" alt="" width="32" height="32" /><span>A little more clarity.<small>With shopops.</small></span></div>
            <div className="illustration-tabs"><span>Overview</span><span>Incidents</span><span>Connections</span></div>
            <div className="illustration-task"><span className="illustration-icon"><BrowserIcon name="list" /></span><div><strong>What needs attention?</strong><p>Capture an issue in your shop</p></div><BrowserIcon name="plus" /></div>
            <div className="illustration-task"><span className="illustration-icon"><BrowserIcon name="globe" /></span><div><strong>Keep the details close</strong><p>Open related pages in tabs</p></div><BrowserIcon name="arrow" /></div>
            <div className="illustration-next"><BrowserIcon name="check" /><span>Know what matters.<br /><strong>Choose your next move.</strong></span></div>
          </div>
        </div>
        <figcaption>Concept illustration · Not live shop data</figcaption>
      </figure>
    </section>

    <section className="landing-features" aria-labelledby="features-title">
      <div className="section-intro"><span className="eyebrow" lang="en">CLARITY IN THE CHAOS</span><h2 id="features-title">Less scattered.<br />More focused.</h2><p>Focus on the work, with the details you need within reach.</p></div>
      <div className="feature-list">
        <article><span className="feature-icon"><BrowserIcon name="list" /></span><div><h3>Capture what needs attention</h3><p>Record and review issues manually. Keep titles, details, and timestamps together for a clearer view.</p></div></article>
        <article><span className="feature-icon"><BrowserIcon name="globe" /></span><div><h3>Keep your place</h3><p>Open multiple workspace tabs. Switch between them without losing each tab’s drafts or history.</p></div></article>
        <article><span className="feature-icon"><BrowserIcon name="check" /></span><div><h3>Explore marketplace connections</h3><p>Try the simulated Shopee, Shopify, and Lazada connection flow. Live marketplace login and data sync are not connected yet.</p></div></article>
      </div>
    </section>

    <section className="landing-steps" id="how-it-works" aria-labelledby="steps-title">
      <span className="eyebrow">A SIMPLE START</span><h2 id="steps-title">From a clearer view to your next move.</h2>
      <ol>
        <li><span className="step-number">01</span><h3>Open your workspace</h3><p>Log in with your workspace access token.</p></li>
        <li><span className="step-number">02</span><h3>See what needs attention</h3><p>Explore demo connections or open the incident log to capture an issue.</p></li>
        <li><span className="step-number">03</span><h3>Choose your next step</h3><p>Review the details, open related pages, and decide how to move forward.</p></li>
      </ol>
    </section>

    <section className="landing-closing" aria-labelledby="closing-title"><div><span className="eyebrow">YOUR NEXT MOVE, MADE CLEAR.</span><h2 id="closing-title">Your everyday operations.<br />A clearer perspective.</h2></div><a className="primary-button" href={href}>{authenticated ? label : 'Open your workspace'}<BrowserIcon name="arrow" /></a></section>
    <footer className="landing-footer"><span>shopops.</span><p>Your shop. Your decisions.</p><a href={href}>{authenticated ? 'Open workspace' : 'Log in'}<BrowserIcon name="arrow" /></a></footer>
  </div>
}

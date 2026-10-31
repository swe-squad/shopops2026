import { useState } from 'react'
import './index.css'

type View = 'overview' | 'incidents' | 'activity' | 'settings'
const navigation: { id: View; icon: string; label: string }[] = [
  { id: 'overview', icon: '◫', label: 'Overview' },
  { id: 'incidents', icon: '◉', label: 'Incidents' },
  { id: 'activity', icon: '◷', label: 'Activity' },
  { id: 'settings', icon: '⚙', label: 'Settings' },
]
const pageCopy: Record<View, { title: string; subtitle: string; empty: string; description: string }> = {
  overview: { title: 'Your shop, in good hands.', subtitle: 'Your operations at a glance, all in one place.', empty: 'A quieter way to run your shop', description: 'Once your shop is connected, your most important updates and recommended actions will appear here.' },
  incidents: { title: 'Incidents', subtitle: 'Keep track of the issues that need your attention.', empty: 'No incidents to show yet', description: 'Detected issues and their recommended next steps will appear here once your shop is connected.' },
  activity: { title: 'Activity', subtitle: 'A running record of your shop operations.', empty: 'Your activity will appear here', description: 'Review updates, decisions, and completed actions in one place after connecting your shop.' },
  settings: { title: 'Settings', subtitle: 'Manage your shop and agent preferences.', empty: 'Your workspace is not connected', description: 'Shop connection and agent settings will be available when the integration is ready.' },
}

function App() {
  const [view, setView] = useState<View>('overview')
  const [client, setClient] = useState<'dashboard' | 'chat'>('dashboard')
  const page = pageCopy[view]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#home" onClick={() => { setView('overview'); setClient('dashboard') }}><span className="brand-mark">✳</span><span>shopops<span className="brand-dot">.</span><small>YOUR SHOP, ON TRACK</small></span></a>
        <div className="workspace"><span className="workspace-icon">S</span><span><strong>My workspace</strong><small>Shop operations</small></span><span className="chevron">⌄</span></div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Workspace navigation">{navigation.map(item => <button key={item.id} className={client === 'dashboard' && view === item.id ? 'nav-item active' : 'nav-item'} onClick={() => { setView(item.id); setClient('dashboard') }}><span className="nav-icon">{item.icon}</span>{item.label}{item.id === 'incidents' && <span className="nav-dash">—</span>}</button>)}</nav>
        <div className="sidebar-bottom"><div className="help-icon">✦</div><strong>Meet your on-call agent</strong><p>Keeping an eye on your shop, so you can focus on growing it.</p><button onClick={() => setClient('chat')}>Open agent chat <span>↗</span></button></div>
        <div className="profile"><span className="avatar">S</span><span><strong>Shop owner</strong><small>Personal workspace</small></span><span className="chevron">⌄</span></div>
      </aside>
      <main className="main-content">
        <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{client === 'chat' ? 'Agent chat' : page.title === 'Your shop, in good hands.' ? 'Overview' : page.title}</strong></div><div className="top-actions"><span className="connection"><i /> Not connected</span><button className="avatar top-avatar" aria-label="Shop owner profile">S</button></div></header>
        <div className="mobile-nav" aria-label="Choose client"><button className={client === 'dashboard' ? 'selected' : ''} onClick={() => setClient('dashboard')}>Dashboard</button><button className={client === 'chat' ? 'selected' : ''} onClick={() => setClient('chat')}>Agent chat</button></div>
        <div className="content-grid"><section className={client === 'chat' ? 'dashboard mobile-hidden' : 'dashboard'}>
          <div className="eyebrow"><span className="sparkle">✳</span> YOUR OPERATIONS WORKSPACE</div>
          <div className="heading-row"><div><h1>{page.title}</h1><p className="subtitle">{page.subtitle}</p></div><span className="date-label">SHOP OVERVIEW <span>↗</span></span></div>
          <div className="status-banner"><div className="status-symbol">✳</div><div><strong>Let’s get your shop connected</strong><p>Connect your shop to start monitoring what matters.</p></div><span className="status-tag">COMING SOON</span></div>
          {view === 'overview' && <><div className="section-heading"><div><span className="section-kicker">THE BIG PICTURE</span><h2>At a glance</h2></div><span className="muted">Live data when connected</span></div><div className="metrics"><div><span>Open incidents</span><strong>—</strong><small><i className="dot orange" /> Awaiting shop data</small></div><div><span>Actions to review</span><strong>—</strong><small><i className="dot blue" /> Awaiting shop data</small></div><div><span>Shop health</span><strong>—</strong><small><i className="dot green" /> Awaiting shop data</small></div></div></>}
          <div className="section-heading lower"><div><span className="section-kicker">{view === 'overview' ? 'NEEDS YOUR ATTENTION' : 'YOUR WORKSPACE'}</span><h2>{view === 'overview' ? 'Recent incidents' : page.title}</h2></div>{view === 'overview' && <button className="text-button" onClick={() => setView('incidents')}>View all <span>→</span></button>}</div>
          <div className="empty-state"><div className="empty-art"><span>✧</span><span>✓</span><span>✦</span></div><h3>{page.empty}</h3><p>{page.description}</p><span className="empty-note">YOUR SHOP DATA WILL APPEAR HERE</span></div>
          <div className="footer-note"><span>✳</span> A little more clarity for every day of business. <span>Made for the people behind the shop.</span></div>
        </section>
        <section className={client === 'dashboard' ? 'chat-panel mobile-hidden' : 'chat-panel'} aria-label="Agent chat preview"><div className="chat-top"><div><span className="section-kicker">YOUR ON-CALL AGENT</span><h2>Always in the loop<span className="brand-dot">.</span></h2><p>Good decisions start with a conversation.</p></div><span className="chat-spark">✳</span></div><div className="phone"><div className="phone-bar"><span>9:41</span><span>● ▰</span></div><div className="chat-header"><span className="back">‹</span><span className="bot-avatar">✳</span><span><strong>ShopOps Agent</strong><small>your shop's on-call assistant</small></span><span className="chat-more">⋮</span></div><div className="chat-body"><div className="day">YOUR AGENT WORKSPACE</div><div className="message"><strong>Hi there! 👋</strong><p>I’m your ShopOps agent. Once your shop is connected, I’ll help you stay on top of the things that need your attention.</p><p>Think of me as an extra pair of eyes for your shop.</p><span>ShopOps Agent</span></div><div className="chat-hint"><span>✦</span><p>Insights, recommendations, and approvals will show up right here.</p></div></div><div className="composer"><span>＋</span><input aria-label="Message" placeholder="Message" disabled /><span>➤</span></div></div><div className="chat-caption"><span className="online-dot" /> CHAT PREVIEW <span>·</span> INTEGRATION COMING SOON</div><button className="switch-dashboard" onClick={() => setClient('dashboard')}>← Back to dashboard</button></section></div>
      </main>
    </div>
  )
}
export default App

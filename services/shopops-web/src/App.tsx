import { useEffect, useState } from 'react'
import { BrowserPane } from './browser-pane'
import { BrowserIcon } from './browser-icon'
import { useNavigationRequests } from './use-navigation-requests'
import { LoginPage } from './login-page'
import { LandingPage } from './landing-page'
import { defaultShopPath, shopDestination, useAppRoute } from './app-route'
import { isLocalShop } from './browser-url'

function BrowserSession({ token }: { token: string }) {
  const navigation = useNavigationRequests(token)
  return <main className="workspace-main standalone-browser">
    {navigation.error && <p className="navigation-warning" role="status">{navigation.error}</p>}
    <BrowserPane token={token} requestedUrl={navigation.request} />
  </main>
}

function App() {
  const [token, setToken] = useState('')
  const { url, navigate, followLink } = useAppRoute()
  const shop = isLocalShop(url)
  const login = url.pathname === '/login'
  const landing = url.pathname === '/'
  const destination = shopDestination(url.searchParams.get('next'))
  const path = `${url.pathname}${url.search}${url.hash}`

  useEffect(() => {
    if (shop && !token) navigate(`/login?next=${encodeURIComponent(shopDestination(path))}`, true)
    else if (login && token) navigate(destination, true)
  }, [shop, login, token, path, destination, navigate])

  useEffect(() => {
    document.documentElement.lang = 'en'
    document.title = shop && token ? 'ShopOps Browser — Your next move, made clear' : login ? 'Log in — ShopOps' : 'ShopOps — Clarity in the chaos'
    document.querySelector<HTMLElement>('.public-content')?.focus()
  }, [path, shop, login, token])

  return <div className={`app-shell${shop && token ? '' : ' public-shell'}`}>
    <header className="workspace-header" onClick={followLink}>
      <a className="brand" href="/" aria-label="ShopOps browser"><img className="brand-mark" src="/brand/mark-primary.svg" alt="" width="24" height="24" /><span>shopops<span className="brand-period">.</span></span></a>
      {shop && token ? <>
        <div className="workspace-heading"><span className="header-divider" aria-hidden="true" /><span>Seller workspace</span></div>
        <button type="button" className="secondary-button lock-button" onClick={() => { setToken(''); navigate('/login', true) }}><BrowserIcon name="lock" />Lock workspace</button>
      </> : <nav className="public-nav" aria-label="Main navigation">
        {landing && <a className="how-link" href="#how-it-works">How it works</a>}
        <a className="secondary-button" href={token ? defaultShopPath : login ? '/' : '/login'}>{token ? 'Open workspace' : login ? 'Back to home' : 'Log in'}</a>
      </nav>}
    </header>
    {shop && token ? <BrowserSession key={path} token={token} /> : <main className="public-content unlock-scroll" tabIndex={-1} onClick={followLink}>
      {login && !token ? <div className="login-layout"><LoginPage key={path} onLogin={value => { setToken(value); navigate(destination, true) }} /><a className="login-home" href="/">← Back to home</a></div>
        : landing ? <LandingPage authenticated={!!token} />
          : !shop && !login ? <section className="unavailable-page"><h1>Page not found</h1><p>The page you are looking for is not here.</p><a href="/">Back to home</a></section> : <p role="status">Redirecting…</p>}
    </main>}
  </div>
}
export default App

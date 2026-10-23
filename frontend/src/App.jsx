import { Routes, Route } from 'react-router-dom'
import Nav from './components/Nav.jsx'
import Footer from './components/Footer.jsx'
import SearchPage from './pages/SearchPage.jsx'
import DetailPage from './pages/DetailPage.jsx'
import AboutPage from './pages/AboutPage.jsx'
import BrowsePage from './pages/BrowsePage.jsx'
import CategoryPage from './pages/CategoryPage.jsx'
import HowPage from './pages/HowPage.jsx'
import FaqPage from './pages/FaqPage.jsx'
import ContactPage from './pages/ContactPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import ComparePage from './pages/ComparePage.jsx'
import BomPage from './pages/BomPage.jsx'
import ChangelogPage from './pages/ChangelogPage.jsx'
import WatchlistPage from './pages/WatchlistPage.jsx'
import StatusPage from './pages/StatusPage.jsx'
import { CompareProvider } from './compare.jsx'
import CompareTray from './components/CompareTray.jsx'
import { useCurrency } from './currency.jsx'

export default function App() {
  // Subscribed only so a currency change re-renders every price on screen.
  useCurrency()
  return (
    <CompareProvider>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <Nav />
        <main style={{ flex: 1 }}>
          <Routes>
            <Route path="/" element={<SearchPage />} />
            {/* Splat, not a named param: a named param stops at the first
                slash, and real MPNs contain them (LM358P/NOPB). */}
            <Route path="/part/*" element={<DetailPage />} />
            <Route path="/browse" element={<BrowsePage />} />
            <Route path="/browse/:slug" element={<CategoryPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/bom" element={<BomPage />} />
            <Route path="/watchlist" element={<WatchlistPage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/how" element={<HowPage />} />
            <Route path="/faq" element={<FaqPage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/changelog" element={<ChangelogPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
        <Footer />
        {/* Last child on purpose: sticky bottom keeps it on screen while
            scrolling and lets it settle below the footer at the end. */}
        <CompareTray />
      </div>
    </CompareProvider>
  )
}

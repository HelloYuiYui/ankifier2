import { NavLink, Route, Routes } from 'react-router-dom'

import { HealthBanner } from './components/HealthBanner'
import { GenerateInput } from './routes/GenerateInput'
import { ManualInput } from './routes/ManualInput'
import { Results } from './routes/Results'
import { Review } from './routes/Review'

const tab = ({ isActive }: { isActive: boolean }) => (isActive ? 'active' : undefined)

export function App() {
  return (
    <>
      <header className="app">
        <h1>Ankifier</h1>
      </header>
      <p className="subtitle">French vocabulary and grammar cards, with audio.</p>

      <nav className="tabs">
        <NavLink to="/" end className={tab}>
          Generate
        </NavLink>
        <NavLink to="/manual" className={tab}>
          Manual
        </NavLink>
        <NavLink to="/review" className={tab}>
          Review
        </NavLink>
        <NavLink to="/results" className={tab}>
          Results
        </NavLink>
      </nav>

      <HealthBanner />

      <Routes>
        <Route path="/" element={<GenerateInput />} />
        <Route path="/manual" element={<ManualInput />} />
        <Route path="/review" element={<Review />} />
        <Route path="/results" element={<Results />} />
        <Route path="*" element={<GenerateInput />} />
      </Routes>
    </>
  )
}

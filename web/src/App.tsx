import { Route, Routes } from 'react-router-dom'

import { HealthBanner } from './components/HealthBanner'
import { GenerateInput } from './routes/GenerateInput'
import { ManualInput } from './routes/ManualInput'
import { Results } from './routes/Results'
import { Review } from './routes/Review'
import Title from './components/Title'
import Navbar from './components/NavBar'

export function App() {
  return (
    <>
      <Title />
      <Navbar />

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

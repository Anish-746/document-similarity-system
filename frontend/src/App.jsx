import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Results from './pages/Results';
import PairDetail from './pages/PairDetail';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="pairs" element={<Results />} />
          <Route path="pairs/:id" element={<PairDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;

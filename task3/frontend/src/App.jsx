import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import SubmitForm from './components/SubmitForm'
import SubmissionsList from './components/SubmissionsList'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-white">
        <nav className="border-b border-slate-200 px-6 py-3 flex gap-6">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `text-sm font-medium ${isActive ? 'text-slate-900' : 'text-slate-400 hover:text-slate-600'}`
            }
          >
            Submit
          </NavLink>
          <NavLink
            to="/submissions"
            className={({ isActive }) =>
              `text-sm font-medium ${isActive ? 'text-slate-900' : 'text-slate-400 hover:text-slate-600'}`
            }
          >
            All submissions
          </NavLink>
        </nav>

        <Routes>
          <Route path="/" element={<SubmitForm />} />
          <Route path="/submissions" element={<SubmissionsList />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
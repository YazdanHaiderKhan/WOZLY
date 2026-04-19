import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, ArrowRight, CheckCircle, Code, Shield, Network } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { useWozlyWebSocket } from '../hooks/useWebSocket'
import { agentsApi } from '../api/agents'
import toast from 'react-hot-toast'

// ── 1. CS Hardcoded Quiz ─────────────────────────────────────────────────────
const CS_QUESTIONS = [
  { q: "What is the time complexity of binary search?", options: ["O(1)", "O(log n)", "O(n)", "O(n^2)"], a: 1 },
  { q: "Which data structure uses LIFO (Last In, First Out)?", options: ["Queue", "Stack", "Tree", "Graph"], a: 1 },
  { q: "What does REST stand for?", options: ["Representational State Transfer", "Remote Execution System Task", "Random Early Stream Test", "Relational Storage Thread"], a: 0 },
  { q: "What is the primary purpose of a foreign key in SQL?", options: ["Speed up queries", "Ensure referential integrity", "Encrypt data", "Auto-increment IDs"], a: 1 },
  { q: "Which pattern restricts instantiation of a class to a single object?", options: ["Factory", "Observer", "Singleton", "Decorator"], a: 2 },
  { q: "What is the average time complexity of QuickSort?", options: ["O(n)", "O(n log n)", "O(n^2)", "O(log n)"], a: 1 },
  { q: "In networking, what layer is responsible for routing?", options: ["Physical", "Data Link", "Network", "Transport"], a: 2 },
  { q: "Which sorting algorithm is inherently stable?", options: ["Merge Sort", "Quick Sort", "Heap Sort", "Selection Sort"], a: 0 },
  { q: "What does ACID stand for in databases?", options: ["Atomicity, Consistency, Isolation, Durability", "Asynchronous, Concurrent, Isolated, Distributed", "Automated, Cached, Indexed, Dynamic", "Available, Consistent, Isolated, Distributed"], a: 0 },
  { q: "What is a closure in JavaScript?", options: ["A function bundled with its lexical environment", "A closed database connection", "A method to end a loop", "A way to hide HTML elements"], a: 0 }
]

export default function Onboarding() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()

  // Wizard State
  const [step, setStep] = useState<'intro' | 'quiz' | 'form' | 'generating'>('intro')
  
  // Quiz State
  const [currentQ, setCurrentQ] = useState(0)
  const [score, setScore] = useState(0)
  
  // Form State
  const [formData, setFormData] = useState({
    domain: '',
    goal: '',
    duration_weeks: 8,
    hours_per_day: 2,
    learning_style: 'project-based'
  })

  // Quiz Logic
  const handleAnswer = (optIndex: number) => {
    if (optIndex === CS_QUESTIONS[currentQ].a) {
      setScore(s => s + 1)
    }
    if (currentQ < CS_QUESTIONS.length - 1) {
      setCurrentQ(c => c + 1)
    } else {
      setStep('form')
    }
  }

  const [progress, setProgress] = useState(0)
  const [progressText, setProgressText] = useState('Running AI Agents...')
  const progressRef = useRef(0)

  useWozlyWebSocket({
    onRoadmapProgress: (payload) => {
      if (step !== 'generating') return
      const next = Math.max(progressRef.current, Math.min(payload.progress ?? 0, 100))
      progressRef.current = next
      setProgress(next)
      if (payload.message) setProgressText(payload.message)
    }
  })

  // Submit Logic
  const handleGenerate = async () => {
    if (!formData.domain || !formData.goal) {
      toast.error("Please fill in what to learn and your goal!")
      return
    }

    setStep('generating')
    setProgress(5)
    progressRef.current = 5
    setProgressText('Starting roadmap generation...')
    const inferredLevel = score >= 8 ? 'advanced' : score >= 5 ? 'intermediate' : 'beginner'

    try {
      await agentsApi.confirmProfile({
        ...formData,
        knowledge_level: inferredLevel
      })
      setProgress(100)
      setProgressText('Roadmap ready')
      toast.success('🎉 Your roadmap is ready!')
      await qc.invalidateQueries({ queryKey: ['cls', user?.user_id] })
      navigate('/dashboard')
    } catch {
      toast.error('Failed to generate roadmap. Please try again.')
      setStep('form')
    }
  }

  return (
    <div className="bg-animated flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-2xl bg-white border border-slate-200 rounded-2xl shadow-xl overflow-hidden min-h-[600px] flex flex-col">
        
        {/* Intro Step */}
        {step === 'intro' && (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <div className="w-16 h-16 rounded-2xl bg-lime-500 text-slate-900 flex items-center justify-center mb-6 shadow-lg shadow-lime-500/20">
              <Brain className="w-8 h-8" />
            </div>
            <h1 className="text-3xl font-extrabold text-slate-900 mb-4">Welcome to Wozly.</h1>
            <p className="text-slate-500 mb-8 max-w-md">Before we generate your customized learning roadmap, let's take a quick 10-question CS assessment to gauge your current level.</p>
            <button onClick={() => setStep('quiz')} className="btn-lime text-lg px-8 py-4">
              Start Assessment <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        )}

        {/* Quiz Step */}
        {step === 'quiz' && (
          <div className="flex-1 flex flex-col p-8">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-2">
                <Code className="w-5 h-5 text-indigo-500" />
                <span className="font-bold text-slate-700">CS Assessment</span>
              </div>
              <span className="text-sm font-semibold text-slate-400">Question {currentQ + 1} of 10</span>
            </div>
            
            <div className="progress-bar mb-12 bg-slate-100">
              <div className="progress-fill bg-indigo-500" style={{ width: `${((currentQ) / 10) * 100}%` }} />
            </div>

            <div className="flex-1">
              <h2 className="text-2xl font-bold text-slate-900 mb-8">{CS_QUESTIONS[currentQ].q}</h2>
              <div className="grid grid-cols-1 gap-3">
                {CS_QUESTIONS[currentQ].options.map((opt, i) => (
                  <button key={i} onClick={() => handleAnswer(i)}
                    className="w-full text-left p-4 rounded-xl border-2 border-slate-100 hover:border-indigo-500 hover:bg-indigo-50/50 transition-all font-medium text-slate-700">
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Form Step */}
        {step === 'form' && (
          <div className="flex-1 flex flex-col p-8">
            <div className="mb-8">
              <h2 className="text-2xl font-extrabold text-slate-900">Configure your roadmap</h2>
              <p className="text-slate-500">You scored {score}/10. We will adapt the curriculum accordingly.</p>
            </div>

            <div className="space-y-5 flex-1">
              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1.5">What do you want to learn?</label>
                <input type="text" placeholder="e.g., Data Structures & Algorithms, React, Rust" className="input-field"
                  value={formData.domain} onChange={e => setFormData({...formData, domain: e.target.value})} />
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1.5">What is your specific goal?</label>
                <input type="text" placeholder="e.g., Crack Google SDE interview, Build a SaaS" className="input-field"
                  value={formData.goal} onChange={e => setFormData({...formData, goal: e.target.value})} />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-1.5">Duration (Weeks)</label>
                  <select className="input-field appearance-none bg-white" 
                    value={formData.duration_weeks} onChange={e => setFormData({...formData, duration_weeks: Number(e.target.value)})}>
                    {[4, 6, 8, 12, 16, 24].map(w => <option key={w} value={w}>{w} weeks</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-1.5">Hours per Day</label>
                  <select className="input-field appearance-none bg-white"
                    value={formData.hours_per_day} onChange={e => setFormData({...formData, hours_per_day: Number(e.target.value)})}>
                    {[1, 2, 3, 4, 6, 8].map(h => <option key={h} value={h}>{h} hours/day</option>)}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1.5">Learning Style</label>
                <div className="grid grid-cols-2 gap-3">
                  <button onClick={() => setFormData({...formData, learning_style: 'project-based'})}
                    className={`p-3 rounded-xl border-2 text-sm font-semibold transition-all ${formData.learning_style === 'project-based' ? 'border-lime-500 bg-lime-50' : 'border-slate-100 text-slate-500'}`}>
                    Project-Based
                  </button>
                  <button onClick={() => setFormData({...formData, learning_style: 'documentation-based'})}
                    className={`p-3 rounded-xl border-2 text-sm font-semibold transition-all ${formData.learning_style === 'documentation-based' ? 'border-lime-500 bg-lime-50' : 'border-slate-100 text-slate-500'}`}>
                    Documentation Heavy
                  </button>
                </div>
              </div>
            </div>

            <button onClick={handleGenerate} className="btn-lime w-full mt-6 py-4 text-base">
              Generate Interactive Roadmap <ArrowRight className="w-5 h-5 ml-2" />
            </button>
          </div>
        )}

        {/* Generating Step */}
        {step === 'generating' && (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <div className="relative mb-8">
              <div className="absolute inset-0 bg-lime-500/20 blur-xl rounded-full animate-pulse" />
              <div className="w-20 h-20 bg-lime-500 rounded-2xl flex items-center justify-center relative z-10 animate-float shadow-2xl shadow-lime-500/30">
                <Brain className="w-10 h-10 text-slate-900" />
              </div>
            </div>
            <h2 className="text-2xl font-extrabold text-slate-900 mb-2">Curating your roadmap...</h2>
            <p className="text-slate-500 mb-8">Searching the web and analyzing resources based on your {score}/10 CS score.</p>
            
            <div className="w-64 max-w-full">
              <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-lime-500"
                  initial={{ width: "0%" }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.4, ease: "easeOut" }}
                />
              </div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-3 animate-pulse">{progressText}</p>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

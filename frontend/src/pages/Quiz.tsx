import { useState, useEffect } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, XCircle, Clock, ChevronRight, Award, AlertCircle, ArrowLeft, Brain } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { assessmentApi } from '../api/agents'
import toast from 'react-hot-toast'

interface Question {
  id: string; type: string; question: string; options?: string[]; correct_answer?: string
}
interface Answer { question_id: string; answer: string }

export default function Quiz() {
  const { weekId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()

  const quizData = location.state?.quiz as { quiz_id: string; questions: Question[] } | null
  // MUST declare questions before any useEffect — const TDZ would crash otherwise
  const questions: Question[] = quizData?.questions ?? []

  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [submitting, setSubmitting] = useState(false)
  const [timeLeft, setTimeLeft] = useState(questions.length * 90)
  const [current, setCurrent] = useState(0)
  const [showFeedback, setShowFeedback] = useState<Record<string, boolean>>({})

  // Timer
  useEffect(() => {
    if (submitted || !quizData) return
    const t = setInterval(() => setTimeLeft(p => { if (p <= 1) { clearInterval(t); return 0 } return p - 1 }), 1000)
    return () => clearInterval(t)
  }, [submitted, quizData])

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        const currentAnswer = answers[questions[current].id]
        if (!currentAnswer) return

        if (current < questions.length - 1) {
          setCurrent(p => p + 1)
        } else if (!submitted && !submitting) {
          submitQuiz()
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [current, answers, questions, submitted, submitting])

  if (!quizData || questions.length === 0) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="bg-white border border-slate-200 rounded-2xl p-8 text-center max-w-sm shadow-sm">
        <AlertCircle className="w-8 h-8 text-rose-500 mx-auto mb-3" />
        <p className="text-slate-600 mb-4">
          {!quizData ? 'No quiz loaded. Please start a quiz from the Dashboard.' : 'This quiz has no questions. Please try again.'}
        </p>
        <button onClick={() => navigate('/dashboard')} className="btn-lime py-2 px-6 rounded-xl text-sm font-bold">Back to Dashboard</button>
      </div>
    </div>
  )

  const q = questions[current]
  const minutes = Math.floor(timeLeft / 60)
  const seconds = timeLeft % 60
  const progress = ((current + 1) / questions.length) * 100

  const selectAnswer = (qid: string, val: string) => {
    if (showFeedback[qid]) return // Don't allow changes after feedback
    setAnswers(prev => ({ ...prev, [qid]: val }))
    // Show feedback immediately
    setShowFeedback(prev => ({ ...prev, [qid]: true }))
  }

  const submitQuiz = async () => {
    const answeredAll = questions.every(q => answers[q.id])
    if (!answeredAll) { toast.error('Please answer all questions before submitting'); return }
    setSubmitting(true)
    try {
      const payload: Answer[] = questions.map(q => ({ question_id: q.id, answer: answers[q.id] ?? '' }))
      const data = await assessmentApi.submitQuiz(quizData.quiz_id, payload)
      setResult(data)
      setSubmitted(true)
    } catch {
      toast.error('Submission failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  // Calculate score for results
  const totalCorrect = result ? Object.values(result.scores as Record<string, number>).filter((s: number) => s >= 0.8).length : 0
  const totalQuestions = questions.length
  const scorePercent = result ? Math.round((Object.values(result.scores as Record<string, number>).reduce((a: number, b: number) => a + b, 0) / totalQuestions) * 100) : 0

  if (submitted && result) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
          className="bg-white border border-slate-200 rounded-2xl shadow-lg w-full max-w-lg p-8 text-center space-y-6">
          
          {/* Score Circle */}
          <div className="relative w-28 h-28 mx-auto">
            <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
              <circle cx="50" cy="50" r="45" fill="none" stroke="#e2e8f0" strokeWidth="8" />
              <circle cx="50" cy="50" r="45" fill="none" 
                stroke={scorePercent >= 70 ? '#84cc16' : '#f43f5e'} 
                strokeWidth="8" strokeLinecap="round"
                strokeDasharray={`${scorePercent * 2.83} ${283 - scorePercent * 2.83}`} />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-black text-slate-900">{scorePercent}%</span>
              <span className="text-[10px] font-bold text-slate-400 uppercase">Score</span>
            </div>
          </div>

          <div>
            <h2 className="text-2xl font-bold text-slate-900">
              {scorePercent >= 70 ? '🎉 Week ' + weekId + ' Complete!' : 'Keep Practicing!'}
            </h2>
            <p className="text-slate-500 mt-1 text-sm">
              You got <span className="font-bold text-slate-900">{totalCorrect}</span> out of <span className="font-bold text-slate-900">{totalQuestions}</span> correct
            </p>
          </div>

          {/* Per-topic breakdown */}
          <div className="space-y-2 text-left">
            {result.mastery_delta.map((d: any) => (
              <div key={d.topic} className="p-3 rounded-xl border border-slate-200 flex items-center gap-3">
                <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                  d.new_score >= 0.8 ? 'bg-lime-500' :
                  d.new_score >= 0.5 ? 'bg-amber-500' : 'bg-rose-500'}`} />
                <span className="text-sm text-slate-700 flex-1 font-medium">{d.topic}</span>
                <span className="text-xs text-slate-400">{(d.previous_score * 100).toFixed(0)}% →</span>
                <span className={`text-sm font-bold ${
                  d.new_score >= 0.8 ? 'text-lime-600' :
                  d.new_score >= 0.5 ? 'text-amber-600' : 'text-rose-600'}`}>
                  {(d.new_score * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>

          <button onClick={() => navigate('/dashboard', { state: { justFinishedQuiz: true, scorePercent, passed: scorePercent >= 60 } })} className="btn-lime w-full py-3 rounded-xl text-sm font-bold">
            <CheckCircle className="w-4 h-4 mr-2 inline" />Back to Dashboard
          </button>
        </motion.div>
      </div>
    )
  }

  // Get correct answer for current question (if it was sent)
  const correctAnswer = q.correct_answer?.trim().toUpperCase() || ''
  const userAnswer = answers[q.id]?.trim().toUpperCase() || ''
  const hasFeedback = showFeedback[q.id]
  const isCorrect = hasFeedback && userAnswer === correctAnswer

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-2xl space-y-4">
        {/* Header */}
        <div className="flex items-center gap-4 bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
          <button onClick={() => navigate('/dashboard')} className="p-2 rounded-lg hover:bg-slate-100 transition-colors">
            <ArrowLeft className="w-4 h-4 text-slate-500" />
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <Brain className="w-4 h-4 text-lime-500" />
              <h1 className="font-bold text-slate-900 text-sm">Week {weekId} Assessment</h1>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-2 flex-1 bg-slate-100 rounded-full overflow-hidden">
                <motion.div className="h-full bg-lime-500 rounded-full" animate={{ width: `${progress}%` }} />
              </div>
              <span className="text-xs font-bold text-slate-500">{current + 1}/{questions.length}</span>
            </div>
          </div>
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border ${timeLeft < 60 ? 'border-rose-300 bg-rose-50' : 'border-slate-200 bg-white'}`}>
            <Clock className={`w-3.5 h-3.5 ${timeLeft < 60 ? 'text-rose-500' : 'text-slate-400'}`} />
            <span className={`text-sm font-mono font-bold ${timeLeft < 60 ? 'text-rose-500' : 'text-slate-700'}`}>
              {minutes}:{seconds.toString().padStart(2, '0')}
            </span>
          </div>
        </div>

        {/* Question card */}
        <AnimatePresence mode="wait">
          <motion.div key={current}
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
            className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-5">
            <div className="flex items-start gap-3">
              <span className={`text-xs px-2.5 py-1 rounded-full border font-bold flex-shrink-0 mt-0.5 ${
                q.type === 'multiple_choice' ? 'border-lime-300 bg-lime-50 text-lime-700' :
                q.type === 'short_answer' ? 'border-blue-300 bg-blue-50 text-blue-700' : 'border-amber-300 bg-amber-50 text-amber-700'}`}>
                {q.type.replace('_', ' ')}
              </span>
              <p className="text-slate-900 font-semibold leading-relaxed">{q.question}</p>
            </div>

            {q.type === 'multiple_choice' && q.options && (
              <div className="space-y-2.5">
                {q.options.map((opt) => {
                  const optLetter = opt[0].toUpperCase()
                  const isSelected = userAnswer === optLetter
                  const isCorrectOption = hasFeedback && correctAnswer === optLetter
                  const isWrongSelection = hasFeedback && isSelected && !isCorrectOption

                  let borderColor = 'border-slate-200 hover:border-slate-300'
                  let bgColor = 'bg-white hover:bg-slate-50'
                  let textColor = 'text-slate-700'
                  let icon = null

                  if (hasFeedback && isCorrectOption) {
                    borderColor = 'border-lime-400'
                    bgColor = 'bg-lime-50'
                    textColor = 'text-lime-800'
                    icon = <CheckCircle className="w-5 h-5 text-lime-500 flex-shrink-0" />
                  } else if (isWrongSelection) {
                    borderColor = 'border-rose-400'
                    bgColor = 'bg-rose-50'
                    textColor = 'text-rose-800'
                    icon = <XCircle className="w-5 h-5 text-rose-500 flex-shrink-0" />
                  } else if (isSelected && !hasFeedback) {
                    borderColor = 'border-slate-900'
                    bgColor = 'bg-slate-50'
                    textColor = 'text-slate-900'
                  }

                  return (
                    <motion.button key={opt} whileHover={!hasFeedback ? { scale: 1.01 } : {}} whileTap={!hasFeedback ? { scale: 0.99 } : {}}
                      onClick={() => selectAnswer(q.id, optLetter)}
                      disabled={hasFeedback}
                      className={`w-full text-left p-4 rounded-xl border-2 text-sm transition-all flex items-center gap-3 ${borderColor} ${bgColor} ${textColor}`}>
                      <span className="flex-1 font-medium">{opt}</span>
                      {icon}
                    </motion.button>
                  )
                })}
                {hasFeedback && (
                  <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}
                    className={`p-3 rounded-lg text-sm font-medium ${isCorrect ? 'bg-lime-100 text-lime-800' : 'bg-rose-100 text-rose-800'}`}>
                    {isCorrect ? '✓ Correct! Well done.' : `✗ Incorrect. The correct answer is ${correctAnswer}.`}
                  </motion.div>
                )}
              </div>
            )}

            {(q.type === 'short_answer' || q.type === 'applied') && (
              <textarea rows={5} placeholder="Type your answer here..."
                className="w-full p-4 border-2 border-slate-200 rounded-xl text-sm text-slate-800 bg-white focus:border-slate-900 focus:outline-none resize-none"
                value={answers[q.id] ?? ''}
                onChange={e => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))} />
            )}
          </motion.div>
        </AnimatePresence>

        {/* Navigation */}
        <div className="flex gap-3">
          {current > 0 && (
            <button onClick={() => setCurrent(p => p - 1)} className="px-5 py-2.5 rounded-xl border-2 border-slate-200 bg-white text-sm font-bold text-slate-700 hover:bg-slate-50">Previous</button>
          )}
          <div className="flex-1" />
          {current < questions.length - 1 ? (
            <button onClick={() => setCurrent(p => p + 1)} disabled={!answers[q.id]} 
              className="px-5 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-bold disabled:opacity-30 hover:bg-slate-800 flex items-center gap-1">
              Next <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button onClick={submitQuiz} disabled={submitting} className="btn-lime px-6 py-2.5 rounded-xl text-sm font-bold flex items-center gap-2">
              {submitting
                ? <div className="w-4 h-4 border-2 border-slate-900/30 border-t-slate-900 rounded-full animate-spin" />
                : <><CheckCircle className="w-4 h-4" />Submit Quiz</>}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

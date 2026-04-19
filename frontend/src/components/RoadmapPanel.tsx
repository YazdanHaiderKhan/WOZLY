import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ChevronRight, BookOpen, CheckCircle, Clock, AlertCircle, ExternalLink, Play } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { assessmentApi } from '../api/agents'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

interface Resource { title: string; url: string; type: string }
interface Section { section_number: number; section_title: string; content?: any; resources?: Resource[]; practice?: any[] }
interface Week {
  week_number: number
  week_title?: string
  week_objective?: string
  topics?: any[]       // old schema
  sections?: Section[] // new schema
  status: 'pending' | 'active' | 'complete'
  resources?: Resource[]
  needs_review?: string[]
  practice_project?: string
}

interface Props { roadmap: { weeks: Week[] } | null; isLoading: boolean }

const STATUS_CONFIG = {
  pending:  { chip: 'chip-pending',  icon: Clock,        label: 'Pending'  },
  active:   { chip: 'chip-active',   icon: Play,         label: 'Active'   },
  complete: { chip: 'chip-complete', icon: CheckCircle,  label: 'Complete' },
}

const TYPE_COLORS: Record<string, string> = {
  video: 'text-rose-400', article: 'text-indigo-400',
  documentation: 'text-emerald-400', exercise: 'text-amber-400',
}

export default function RoadmapPanel({ roadmap, isLoading }: Props) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState<number | null>(1)
  const [quizLoading, setQuizLoading] = useState<number | null>(null)

  const startQuiz = async (weekNum: number) => {
    if (!user) return
    setQuizLoading(weekNum)
    try {
      const data = await assessmentApi.generateQuiz(user.user_id, weekNum)
      navigate(`/quiz/${weekNum}`, { state: { quiz: data } })
    } catch {
      toast.error('Failed to generate quiz')
    } finally {
      setQuizLoading(null)
    }
  }

  if (isLoading) return (
    <div className="space-y-3">
      {[1,2,3].map(i => (
        <div key={i} className="glass h-16 shimmer rounded-xl" />
      ))}
    </div>
  )

  if (!roadmap?.weeks?.length) return (
    <div className="glass p-6 text-center">
      <BookOpen className="w-8 h-8 text-slate-600 mx-auto mb-2" />
      <p className="text-sm text-slate-500">No roadmap yet — complete onboarding first</p>
    </div>
  )

  const completed = roadmap.weeks.filter(w => w.status === 'complete').length
  const total = roadmap.weeks.length

  return (
    <div className="space-y-3">
      {/* Overall progress */}
      <div className="glass p-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-slate-400 font-medium">Overall Progress</span>
          <span className="text-xs text-indigo-400 font-bold">{completed}/{total} weeks</span>
        </div>
        <div className="progress-bar">
          <motion.div className="progress-fill" initial={{ width: 0 }}
            animate={{ width: `${(completed / total) * 100}%` }} transition={{ duration: 0.8, delay: 0.2 }} />
        </div>
      </div>

      {/* Week cards */}
      {roadmap.weeks.map((week) => {
        const isOpen = expanded === week.week_number
        const cfg = STATUS_CONFIG[week.status] ?? STATUS_CONFIG.pending
        const Icon = cfg.icon
        const needsReview = (week.needs_review ?? []).length > 0

        return (
          <motion.div key={week.week_number} layout className="glass glass-hover overflow-hidden">
            {/* Week header */}
            <button className="w-full flex items-center gap-3 p-4 text-left"
              onClick={() => setExpanded(isOpen ? null : week.week_number)}>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold
                ${week.status === 'complete' ? 'bg-emerald-500/20 text-emerald-400' :
                  week.status === 'active' ? 'bg-indigo-500/20 text-indigo-400' :
                  'bg-slate-700/50 text-slate-500'}`}>
                {week.week_number}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-200">{week.week_title || `Week ${week.week_number}`}</span>
                  <span className={cfg.chip}><Icon className="w-3 h-3" />{cfg.label}</span>
                  {needsReview && <span className="chip-review"><AlertCircle className="w-3 h-3" />Review</span>}
                </div>
                <p className="text-xs text-slate-500 truncate mt-0.5">
                  {(week.sections ?? []).slice(0, 3).map((s: Section) => s.section_title).join(' · ')
                   || (week.topics ?? []).slice(0, 3).map((t: any) => typeof t === 'string' ? t : t?.name || '').join(' · ')
                   || week.week_objective || ''}
                </p>
              </div>
              <motion.div animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown className="w-4 h-4 text-slate-500" />
              </motion.div>
            </button>

            {/* Expanded content */}
            <AnimatePresence>
              {isOpen && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }}>
                  <div className="px-4 pb-4 space-y-3 border-t border-white/5 pt-3">
                    {/* Sections / Topics */}
                    <div className="flex flex-wrap gap-2">
                      {(week.sections
                        ? week.sections.map((s: Section) => s.section_title)
                        : (week.topics ?? []).map((t: any) => typeof t === 'string' ? t : t?.name || '')
                      ).map((label: string) => {
                        const isNeedsReview = week.needs_review?.includes(label)
                        return (
                          <span key={label} className={`text-xs px-2.5 py-1 rounded-full border
                            ${isNeedsReview
                              ? 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                              : 'bg-indigo-500/10 border-indigo-500/20 text-indigo-300'}`}>
                            {label}
                          </span>
                        )
                      })}
                    </div>

                    {/* Practice Project */}
                    {week.practice_project && (
                      <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-lg p-3 mt-2">
                        <p className="text-xs text-indigo-400 font-semibold mb-1 flex items-center gap-1.5">
                          <AlertCircle className="w-3.5 h-3.5" /> Practice Project
                        </p>
                        <p className="text-xs text-slate-300 leading-relaxed">
                          {week.practice_project}
                        </p>
                      </div>
                    )}

                    {/* Resources */}
                    {(week.resources?.length ?? 0) > 0 && (
                      <div className="space-y-1.5 mt-2">
                        <p className="text-xs text-slate-500 font-medium mb-1">Resources</p>
                        {week.resources?.map((r, i) => (
                          <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                            className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-200 transition-colors group">
                            <span className={`text-xs font-medium uppercase ${TYPE_COLORS[r.type] ?? 'text-slate-500'}`}>
                              {r.type.slice(0, 3)}
                            </span>
                            <span className="flex-1 truncate group-hover:underline">{r.title}</span>
                            <ExternalLink className="w-3 h-3 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                          </a>
                        ))}
                      </div>
                    )}

                    {/* Quiz button */}
                    {week.status !== 'pending' && (
                      <button onClick={() => startQuiz(week.week_number)}
                        disabled={quizLoading === week.week_number}
                        className="btn-primary text-xs py-2 px-4 w-full mt-1">
                        {quizLoading === week.week_number
                          ? <div className="w-3 h-3 border border-white/30 border-t-white rounded-full animate-spin" />
                          : <><CheckCircle className="w-3 h-3" />Take Week {week.week_number} Quiz</>}
                      </button>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )
      })}
    </div>
  )
}

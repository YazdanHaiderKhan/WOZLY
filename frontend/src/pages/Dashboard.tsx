import { useState, useEffect } from 'react'
import { Brain, ExternalLink, CheckCircle, Lock, ArrowRight, RotateCcw, BookOpen, Target, Compass, Zap, ChevronDown, ChevronRight as ChevronRightIcon, Sparkles, Loader2 } from 'lucide-react'

import { useAuth } from '../hooks/useAuth'
import { useCLS, clearRoadmapCache } from '../hooks/useCLS'
import { useWozlyWebSocket } from '../hooks/useWebSocket'
import { Navigate, useNavigate, useLocation } from 'react-router-dom'
import TutorChat from '../components/TutorChat'
import toast from 'react-hot-toast'
import { motion, AnimatePresence } from 'framer-motion'


function getTopicContent(topic: string, idx: number) {
  return {
    overview: idx === 0
      ? `${topic} forms the foundation of this week's curriculum. Understanding these principles is critical before moving to more advanced topics. Focus on building strong mental models — not just memorizing definitions.`
      : idx === 1
      ? `${topic} builds upon the fundamentals. Here you'll explore how these ideas connect and interact in practice. Pay special attention to common patterns and anti-patterns.`
      : `${topic} ties everything together. This is where theory meets practice. By the end of this section, you should be comfortable working hands-on with these tools and techniques.`,
    key_points: [
      `Understand the core principles behind ${topic}`,
      `Learn common patterns and best practices`,
      `Apply concepts through practical exercises`,
      `Build confidence for the weekly assessment`,
    ],
    example_code: idx === 0
      ? `// Getting Started with ${topic}\n// Step 1: Understand the problem space\n// Step 2: Break it into smaller sub-problems\n// Step 3: Apply ${topic} principles\n// Step 4: Verify your solution works correctly\n\nfunction learn(concept) {\n  const understanding = study(concept);\n  const practice = apply(understanding);\n  return master(practice);\n}`
      : idx === 1
      ? `// Practical Exercise: ${topic}\n// Try implementing a small project:\n\nclass ${topic.replace(/[^a-zA-Z]/g, '')}Module {\n  constructor() {\n    this.concepts = [];\n    this.mastery = 0;\n  }\n\n  addConcept(name, difficulty) {\n    this.concepts.push({ name, difficulty });\n  }\n\n  practice() {\n    this.mastery += 10;\n    return this.mastery;\n  }\n}`
      : `// Hands-on: ${topic}\n// Set up your environment and experiment\n\nasync function setupEnvironment() {\n  // 1. Install required tools\n  // 2. Configure your workspace\n  // 3. Run the starter template\n  // 4. Modify and experiment!\n  \n  console.log("Ready to learn ${topic}!");\n}`,
  }
}

export default function Dashboard() {
  const { user } = useAuth()
  const { roadmap, mastery, isLoading, refetch } = useCLS()
  const [bgProgress, setBgProgress] = useState<{progress: number, message: string} | null>(null)
  
  useWozlyWebSocket({
    onRoadmapProgress: (payload) => {
      setBgProgress({ progress: payload.progress, message: payload.message ?? '' })
      if (payload.progress === 100) {
        refetch()
        setTimeout(() => setBgProgress(null), 4000)
      }
    }
  })

  const navigate = useNavigate()
  const location = useLocation()

  const [expandedTopic, setExpandedTopic] = useState<number | null>(null)
  const [completedTopics, setCompletedTopics] = useState<Set<string>>(new Set())

  // Show motivational popups upon returning from a quiz
  // Must be here (before early returns) — hooks cannot be after conditional returns
  useEffect(() => {
    const state = location.state as any
    if (state?.justFinishedQuiz) {
      refetch()
      if (state.passed) {
        toast.success(`🎉 Congratulations! You scored ${state.scorePercent}% and cleared the 60% mark! The next module is unlocked.`, { duration: 6000 })
      } else {
        toast(`💪 You scored ${state.scorePercent}%. Keep studying and try again to clear the 60% passing mark!`, { icon: '🔥', duration: 6000 })
      }
      window.history.replaceState({}, document.title)
    }
  }, [location, refetch])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center">
        <div className="w-8 h-8 border-4 border-lime-500/30 border-t-lime-500 rounded-full animate-spin" />
        <p className="mt-4 text-sm font-bold text-slate-500 uppercase tracking-widest">Loading Dashboard...</p>
      </div>
    )
  }

  if (!isLoading && (!roadmap?.weeks || !Array.isArray(roadmap.weeks) || roadmap.weeks.length === 0)) {
    return <Navigate to="/onboarding" replace />
  }

  const weeks = Array.isArray(roadmap?.weeks) ? roadmap.weeks : []
  const completed = weeks.filter((w: any) => w?.status === 'complete').length
  const total = weeks.length
  const overallPct = total ? Math.round((completed / total) * 100) : 0

  const masteryEntries = mastery ? Object.entries(mastery) : []
  const avgMastery = masteryEntries.length
    ? Math.round(masteryEntries.reduce((s, [, v]: any) => s + (v.current_score || 0), 0) / masteryEntries.length * 100)
    : 0

  const activeWeek = weeks.find((w: any) => w.status === 'active') || weeks[0]
  const activeWeekNum = activeWeek?.week_number || 1
  
  // Support both new schema (sections) and old schema (topics)
  const rawSections = Array.isArray(activeWeek?.sections) ? activeWeek.sections : []
  const rawTopics = Array.isArray(activeWeek?.topics) ? activeWeek.topics : []

  const activeTopics: any[] = rawSections.length > 0
    // NEW SCHEMA: sections with content
    ? rawSections.map((s: any) => ({
        id: s.section_title || `section-${s.section_number}`,
        name: s.section_title || `Section ${s.section_number}`,
        overview: s.content?.explanation || `Learn about ${s.section_title} in this section.`,
        key_points: Array.isArray(s.content?.key_points) ? s.content.key_points : [],
        example_code: s.content?.code_example?.code || s.content?.example_code || null,
        code_language: s.content?.code_example?.language || 'javascript',
        code_caption: s.content?.code_example?.caption || '',
        resources: Array.isArray(s.resources) ? s.resources : [],
        practice: Array.isArray(s.practice) ? s.practice : [],
      }))
    // OLD SCHEMA: topics as strings or objects
    : rawTopics.map((t: any, idx: number) => {
        if (t && typeof t === 'object' && !Array.isArray(t)) {
          const rawName = t.name || t.title || t.topic || 'Unknown Topic'
          const name = typeof rawName === 'string' ? rawName : JSON.stringify(rawName)
          return {
            id: name, name,
            overview: typeof t.overview === 'string' ? t.overview : 'Learn about this topic.',
            key_points: Array.isArray(t.key_points) ? t.key_points : [],
            example_code: t.example_code || '// No example code provided.',
            resources: [], practice: [], code_language: 'javascript', code_caption: '',
          }
        }
        const name = t ? String(t) : `Topic ${idx + 1}`
        const content = getTopicContent(name, idx)
        return {
          id: name, name,
          overview: content.overview,
          key_points: content.key_points,
          example_code: content.example_code,
          resources: [], practice: [], code_language: 'javascript', code_caption: '',
        }
      })


  // Calculate real progress
  const topicsCompleted = activeTopics.filter((t: any) => completedTopics.has(t.id) || (mastery?.[t.id]?.current_score || 0) >= 0.6).length
  const activeWeekProgress = activeTopics.length > 0 ? Math.round((topicsCompleted / activeTopics.length) * 100) : 0


  const toggleComplete = (topic: string) => {
    setCompletedTopics(prev => {
      const next = new Set(prev)
      if (next.has(topic)) next.delete(topic)
      else next.add(topic)
      return next
    })
  }

  const isTopicComplete = (topicId: string) => completedTopics.has(topicId) || (mastery?.[topicId]?.current_score || 0) >= 0.6

  // Get resources for a topic — reads per-section resources (new schema)
  // Falls back to distributing week-level resources (old schema)
  const getTopicResources = (topic: any) => {
    // New schema: resources are stored directly on the section/topic object
    if (Array.isArray(topic.resources) && topic.resources.length > 0) {
      return topic.resources
    }
    // Old schema fallback: distribute week-level resources
    const allResources = Array.isArray(activeWeek?.resources) ? activeWeek.resources : []
    if (allResources.length === 0 || activeTopics.length === 0) return []
    const topicIdx = activeTopics.findIndex((t: any) => t.id === topic.id)
    const perTopic = Math.ceil(allResources.length / activeTopics.length)
    return allResources.slice(topicIdx * perTopic, (topicIdx + 1) * perTopic)
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Navbar */}
      <nav className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-2">
          <Brain className="w-6 h-6 text-lime-500" />
          <span className="font-serif text-xl tracking-tight text-slate-900">Wozly</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="px-3 py-1 rounded-full border border-slate-200 text-xs font-semibold text-slate-600 bg-slate-50">
            {roadmap?.domain || 'Computer Science'} - {roadmap?.goal || 'Learning Path'}
          </div>
          <div className="px-3 py-1 rounded-full bg-slate-900 text-xs font-semibold text-white">
            {roadmap?.knowledge_level || 'Beginner'}
          </div>
          <div className="px-3 py-1 rounded-full bg-lime-500 text-xs font-bold text-slate-900">
            Week {activeWeekNum} of {total}
          </div>
          <div className="w-8 h-8 rounded-full bg-slate-900 flex items-center justify-center text-xs font-bold text-white ml-2">
            {user?.name?.[0]?.toUpperCase()}
          </div>
          <button 
            onClick={async () => {
              const { agentsApi } = await import('../api/agents')
              if (user?.user_id) clearRoadmapCache(user.user_id)
              await agentsApi.resetProfile()
              await refetch()
              navigate('/onboarding')
            }}
            className="ml-4 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-rose-50 text-rose-600 hover:bg-rose-100 transition-colors text-xs font-bold border border-rose-200"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reset Demo
          </button>
        </div>
      </nav>

      {/* Curation Progress Banner */}
      {bgProgress && (
        <div className="w-full bg-slate-900 border-b border-slate-700 px-6 py-3 flex items-center gap-4">
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="w-4 h-4 border-2 border-lime-400/40 border-t-lime-400 rounded-full animate-spin" />
            <span className="text-xs font-bold text-lime-400 uppercase tracking-widest">Curating Content</span>
          </div>
          <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-lime-400 rounded-full transition-all duration-700 ease-out"
              style={{ width: `${bgProgress.progress}%` }}
            />
          </div>
          <span className="text-xs text-slate-400 flex-shrink-0 w-8 text-right">{bgProgress.progress}%</span>
          <span className="text-xs text-slate-500 flex-shrink-0 max-w-xs truncate">{bgProgress.message}</span>
        </div>
      )}

      {/* Main Layout Grid */}
      <div className="flex-1 flex max-w-[1600px] w-full mx-auto p-6 gap-6">
        
        {/* Left Sidebar - Timeline */}
        <div className="w-[300px] flex-shrink-0 flex flex-col">
          <div className="mb-8">
            <h3 className="text-[10px] font-bold text-slate-400 tracking-widest uppercase mb-2">Your Goal</h3>
            <p className="text-sm font-semibold text-slate-800 leading-tight mb-4">
              {roadmap?.goal || 'Complete the learning path'} - {total} weeks
            </p>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-slate-500">{completed} of {total} weeks complete</span>
              <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-slate-900 text-white">{overallPct}%</span>
            </div>
            <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
              <div className="h-full bg-slate-900 transition-all duration-500" style={{ width: `${overallPct}%` }} />
            </div>
          </div>

          <div className="space-y-6 relative before:absolute before:inset-0 before:ml-2.5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-slate-200 before:via-slate-200 before:to-transparent">
            {weeks.map((week: any, idx: number) => {
              const isComplete = week.status === 'complete'
              const isActive = week.status === 'active'
              const isLocked = !isComplete && !isActive
              // Support new schema (sections) and old schema (topics)
              const sectionTitles = Array.isArray(week.sections)
                ? week.sections.map((s: any) => s.section_title || '')
                : []
              const rawWeekTopics = Array.isArray(week.topics) ? week.topics : []
              let previewName = week.week_title || 'Upcoming'
              if (!week.week_title) {
                const first = sectionTitles[0] || rawWeekTopics[0]
                if (typeof first === 'string') previewName = first
                else if (first?.name) previewName = first.name
                else if (first?.title) previewName = first.title
              }

              return (
                <div key={idx} className={`relative flex items-start gap-4 ${isLocked ? 'opacity-40' : ''}`}>
                  <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center z-10 bg-white
                    ${isComplete ? 'border-slate-900' : isActive ? 'border-lime-500 bg-lime-500' : 'border-slate-300 bg-slate-100'}`}>
                    {isComplete && <CheckCircle className="w-3 h-3 text-slate-900" />}
                    {isLocked && <Lock className="w-2.5 h-2.5 text-slate-400" />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className={`text-xs font-bold uppercase tracking-wider ${isActive ? 'text-slate-900' : 'text-slate-400'}`}>Week {week.week_number}</p>
                      {isLocked && <span className="text-[9px] font-bold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">LOCKED</span>}
                    </div>
                    <p className={`text-sm font-semibold mt-0.5 ${isActive ? 'text-slate-900' : isComplete ? 'text-slate-700' : 'text-slate-400'}`}>
                      {previewName}
                    </p>
                    {isActive && (
                      <div className="mt-2">
                        <div className="flex justify-between mb-1">
                          <span className="text-[10px] font-semibold text-slate-500">Progress</span>
                          <span className="text-[10px] font-bold text-slate-700">{topicsCompleted}/{activeTopics.length} topics</span>
                        </div>
                        <div className="h-1 w-32 bg-slate-200 rounded-full"><div className="h-full bg-lime-500 rounded-full transition-all duration-500" style={{ width: `${activeWeekProgress}%` }} /></div>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Center Main Content */}
        <div className="flex-1 min-w-0 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-y-auto p-8 flex flex-col gap-6">
          
          {/* Background Task Notification */}
          <AnimatePresence>
            {bgProgress && bgProgress.progress < 100 && (
              <motion.div 
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="mb-6 p-4 rounded-xl bg-slate-900 text-white shadow-2xl border border-slate-700 flex items-center gap-4"
              >
                <div className="w-10 h-10 rounded-full bg-lime-500 flex items-center justify-center flex-shrink-0 animate-pulse">
                  <Sparkles className="w-5 h-5 text-slate-900" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-center mb-1.5">
                    <p className="text-xs font-bold uppercase tracking-widest text-lime-400">Deep Curator Active</p>
                    <span className="text-[10px] font-mono text-slate-400">{bgProgress.progress}%</span>
                  </div>
                  <p className="text-sm font-semibold truncate">{bgProgress.message}</p>
                  <div className="mt-2 h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                    <motion.div 
                      className="h-full bg-lime-500"
                      initial={{ width: 0 }}
                      animate={{ width: `${bgProgress.progress}%` }}
                    />
                  </div>
                </div>
                <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Module Header */}

          <div className="pb-6 border-b border-slate-100">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
              Week {activeWeekNum} · {activeTopics.length} Topics
            </p>
            <h1 className="text-3xl font-serif text-slate-900 mb-3">{activeWeek?.practice_project ? "Project Week" : (activeTopics[0]?.name || 'Module')}</h1>
            
            <div className="flex items-center gap-6 mb-4">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-lime-500" />
                <span className="text-xs font-semibold text-slate-600">{topicsCompleted} of {activeTopics.length} completed</span>
              </div>
              <div className="h-2 flex-1 max-w-[200px] bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-lime-500 rounded-full transition-all duration-500" style={{ width: `${activeWeekProgress}%` }} />
              </div>
              <span className="text-xs font-bold text-slate-900">{activeWeekProgress}%</span>
            </div>

            {/* Quick info cards */}
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-lime-50 border border-lime-200">
                <Target className="w-4 h-4 text-lime-700 mb-1" />
                <p className="text-[10px] font-bold text-lime-800 uppercase">Objective</p>
                <p className="text-xs text-slate-600 mt-1">Master all {activeTopics.length} topics to unlock next week</p>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <Compass className="w-4 h-4 text-slate-600 mb-1" />
                <p className="text-[10px] font-bold text-slate-600 uppercase">Approach</p>
                <p className="text-xs text-slate-600 mt-1">Read → Practice → Ask Tutor → Take Assessment</p>
              </div>
              <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
                <Zap className="w-4 h-4 text-amber-600 mb-1" />
                <p className="text-[10px] font-bold text-amber-700 uppercase">Outcome</p>
                <p className="text-xs text-slate-600 mt-1">Pass the assessment with ≥70% to advance</p>
              </div>
            </div>
          </div>

          {/* Topic Cards */}
          <div className="space-y-3">
            {activeTopics.map((topic: any, i: number) => {
              const isExpanded = expandedTopic === i
              const isDone = isTopicComplete(topic.id)
              const topicResources = getTopicResources(topic)
              const topicMastery = mastery?.[topic.id]?.current_score ? Math.round(mastery?.[topic.id]?.current_score * 100) : 0

              return (
                <div key={i} className={`rounded-xl border-2 transition-all duration-300 overflow-hidden
                  ${isDone ? 'border-lime-300 bg-lime-50/30' : isExpanded ? 'border-slate-300 bg-white shadow-lg' : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm'}`}>
                  
                  {/* Card Header - Always visible */}
                  <button onClick={() => setExpandedTopic(isExpanded ? null : i)} className="w-full flex items-center gap-4 p-5 text-left">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold flex-shrink-0
                      ${isDone ? 'bg-lime-500 text-white' : 'bg-slate-100 text-slate-600'}`}>
                      {isDone ? <CheckCircle className="w-4 h-4" /> : i + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-slate-900">{typeof topic.name === 'string' ? topic.name : 'Topic'}</p>
                      <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">
                        {topic.key_points?.[0] || (typeof topic.overview === 'string' ? topic.overview.slice(0, 90) + '…' : '')}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      {topicMastery > 0 && (
                        <span className="text-xs font-bold text-slate-500">{topicMastery}%</span>
                      )}
                      <span className={`text-[10px] font-bold px-2 py-1 rounded-full 
                        ${isDone ? 'bg-lime-100 text-lime-700' : 'bg-slate-100 text-slate-500'}`}>
                        {isDone ? '✓ Completed' : 'Not started'}
                      </span>
                      {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRightIcon className="w-4 h-4 text-slate-400" />}
                    </div>
                  </button>

                  {/* Expanded Content */}
                  {isExpanded && (
                    <div className="px-5 pb-6 border-t border-slate-100 pt-5 space-y-6">
                      {!topic.overview ? (
                        <div className="py-8 text-center space-y-4">
                          <div className="w-8 h-8 border-2 border-lime-500/30 border-t-lime-500 rounded-full animate-spin mx-auto" />
                          <div className="space-y-1">
                            <p className="text-sm font-bold text-slate-800">Generating curated content...</p>
                            <p className="text-[10px] text-slate-500">Our AI is building your masterclass guide.</p>
                          </div>
                        </div>
                      ) : (
                        <>
                          {/* Overview */}
                          <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                              <span className="w-1.5 h-1.5 rounded-full bg-lime-500 inline-block" />
                              Overview
                            </h4>
                            <p className="text-sm text-slate-700 leading-relaxed">{topic.overview}</p>
                          </div>

                          {/* Key Points */}
                          {topic.key_points?.length > 0 && (
                            <div>
                              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 inline-block" />
                                Key Takeaways
                              </h4>
                              <div className="grid grid-cols-1 gap-2">
                                {topic.key_points.map((point: any, pi: number) => (
                                  <div key={pi} className="flex items-start gap-3 p-3 rounded-lg bg-indigo-50/60 border border-indigo-100">
                                    <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-600 text-[10px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5">{pi + 1}</span>
                                    <p className="text-xs text-slate-700 leading-relaxed">{typeof point === 'string' ? point : JSON.stringify(point)}</p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Code Example */}
                          {topic.example_code && (
                            <div>
                              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                                Code Example
                              </h4>
                              {topic.code_caption && (
                                <p className="text-xs text-slate-500 italic mb-2">{topic.code_caption}</p>
                              )}
                              <div className="rounded-xl bg-slate-900 border border-slate-700 overflow-hidden">
                                <div className="flex items-center justify-between px-4 py-2 bg-slate-800 border-b border-slate-700">
                                  <div className="flex gap-1.5">
                                    <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
                                    <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/70" />
                                    <div className="w-2.5 h-2.5 rounded-full bg-green-500/70" />
                                  </div>
                                  <span className="text-[10px] font-mono text-slate-500">{topic.code_language}</span>
                                </div>
                                <pre className="p-4 overflow-x-auto"><code className="text-emerald-400 text-xs font-mono leading-relaxed">{topic.example_code}</code></pre>
                              </div>
                            </div>
                          )}

                          {/* Practice */}
                          {topic.practice?.length > 0 && (
                            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                              <h4 className="text-[10px] font-bold text-amber-700 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                                <Zap className="w-3 h-3" />
                                Practice Task{topic.practice.length > 1 ? 's' : ''}
                              </h4>
                              <div className="space-y-3">
                                {topic.practice.map((p: any, pi: number) => (
                                  <div key={pi} className="flex items-start gap-3">
                                    <span className="text-amber-500 font-bold text-sm flex-shrink-0">{pi + 1}.</span>
                                    <p className="text-sm text-slate-700 leading-relaxed">{typeof p === 'string' ? p : p.question}</p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      )}

                      {/* Resources */}
                      {topicResources.length > 0 && (
                        <div>
                          <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-rose-400 inline-block" />
                            Resources
                          </h4>
                          <div className="space-y-2">
                            {topicResources.map((r: any, ri: number) => (
                              <a key={ri} href={r.url} target="_blank" rel="noopener noreferrer"
                                className="flex items-center gap-3 p-3 rounded-lg border border-slate-100 hover:border-lime-300 hover:bg-lime-50/50 transition-all group">
                                <div className="w-8 h-8 rounded-lg bg-slate-100 group-hover:bg-lime-100 flex items-center justify-center flex-shrink-0">
                                  <ExternalLink className="w-3.5 h-3.5 text-slate-400 group-hover:text-lime-600" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs font-semibold text-slate-800 group-hover:text-lime-800 truncate">{typeof r.title === 'string' ? r.title : 'Resource'}</p>
                                  <div className="flex items-center gap-2 mt-0.5">
                                    <span className="text-[10px] text-slate-400 capitalize">{typeof r.type === 'string' ? r.type : 'article'}</span>
                                    {r.duration_minutes && <span className="text-[10px] text-slate-400">· {r.duration_minutes} min</span>}
                                  </div>
                                </div>
                                <ArrowRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-lime-500 flex-shrink-0" />
                              </a>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Mark as Complete */}
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleComplete(topic.id) }}
                        className={`w-full py-3 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2
                          ${isDone
                            ? 'bg-lime-100 text-lime-700 border-2 border-lime-300 hover:bg-white'
                            : 'bg-slate-900 text-white hover:bg-slate-700'}`}>
                        <CheckCircle className="w-4 h-4" />
                        {isDone ? 'Marked as Complete ✓' : 'Mark as Complete'}
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Weekly Assessment */}
          {(() => {
            const allDone = topicsCompleted >= activeTopics.length && activeTopics.length > 0
            const remaining = activeTopics.length - topicsCompleted
            return (
              <div className={`p-6 rounded-xl border-2 flex flex-col items-center text-center mt-4 transition-all
                ${allDone ? 'border-lime-300 bg-lime-50/60' : 'border-slate-200 bg-slate-50/60'}`}>
                <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-3
                  ${allDone ? 'bg-lime-500' : 'bg-slate-200'}`}>
                  {allDone
                    ? <CheckCircle className="w-5 h-5 text-white" />
                    : <Lock className="w-5 h-5 text-slate-400" />}
                </div>
                <h3 className={`text-xs font-bold uppercase tracking-widest mb-2
                  ${allDone ? 'text-lime-700' : 'text-slate-500'}`}>
                  Weekly Assessment
                </h3>
                <p className="text-sm font-semibold text-slate-800 mb-2 max-w-md">
                  {allDone
                    ? 'All sections complete! Take the assessment to unlock the next week.'
                    : `Complete ${remaining} more section${remaining !== 1 ? 's' : ''} to unlock the assessment.`}
                </p>

                {/* Section completion mini-bar */}
                <div className="w-full max-w-xs mb-5">
                  <div className="flex justify-between text-[10px] text-slate-500 mb-1.5">
                    <span>Sections done</span>
                    <span className="font-bold">{topicsCompleted}/{activeTopics.length}</span>
                  </div>
                  <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-500
                      ${allDone ? 'bg-lime-500' : 'bg-slate-400'}`}
                      style={{ width: `${activeWeekProgress}%` }} />
                  </div>
                </div>

                <button
                  disabled={!allDone}
                  className={`text-sm py-3 px-6 rounded-xl font-bold flex items-center gap-2 transition-all
                    ${allDone
                      ? 'bg-slate-900 text-white hover:bg-slate-700 shadow-lg cursor-pointer'
                      : 'bg-slate-200 text-slate-400 cursor-not-allowed'}`}
                  onClick={async () => {
                    if (!allDone || !user?.user_id) return
                    const toastId = toast.loading('Generating adaptive assessment...')
                    try {
                      const { assessmentApi } = await import('../api/agents')
                      const quizData = await assessmentApi.generateQuiz(user.user_id, activeWeekNum)
                      toast.dismiss(toastId)
                      navigate(`/quiz/${activeWeekNum}`, { state: { quiz: quizData } })
                    } catch (error) {
                      toast.error('Failed to generate assessment. Try again.', { id: toastId })
                    }
                  }}
                >
                  {allDone ? <>Take Assessment <ArrowRight className="w-4 h-4" /></> : <><Lock className="w-4 h-4" /> Complete All Sections First</>}
                </button>
              </div>
            )
          })()}
        </div>

        {/* Right Sidebar */}
        <div className="w-[320px] flex-shrink-0 flex flex-col gap-4">
          <div className="flex gap-4 h-[240px]">
            <div className="flex-1 dark-panel p-6 flex flex-col">
              <h2 className="text-4xl font-extrabold mb-2">{avgMastery}%</h2>
              <p className="text-xs text-slate-400 font-medium">Overall mastery</p>
              <div className="mt-auto text-[10px] text-slate-500 font-mono space-y-1">
                <p>WEEK {activeWeekNum}</p>
                <p>Topics: {activeTopics.length}</p>
                <p>Done: {topicsCompleted}</p>
                <p>Progress: {activeWeekProgress}%</p>
              </div>
            </div>
            <div className="flex-1 lime-panel p-6 flex flex-col justify-between relative overflow-hidden">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider mb-2 text-slate-800">Active Week</p>
                <h2 className="text-5xl font-black text-slate-900 tracking-tighter">
                  {activeWeekNum < 10 ? `0${activeWeekNum}` : activeWeekNum}
                </h2>
              </div>
              <p className="text-xs font-semibold text-slate-800 leading-tight">
                {activeTopics[0]?.name || 'Topic'},<br/>
                {activeTopics.slice(1, 3).map(t => t.name).join(' - ')}
              </p>
              <ArrowRight className="absolute bottom-4 right-4 w-5 h-5 text-slate-900 opacity-50" />
            </div>
          </div>

          <div className="flex-1 dark-panel overflow-hidden flex flex-col min-h-[400px]">
            <TutorChat currentTopic={activeTopics[0]?.name || null} />
          </div>
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowLeft, Save, Trash2, User, Target, Clock, Brain } from 'lucide-react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useCLS } from '../hooks/useCLS'
import { userApi } from '../api/agents'
import { roadmapApi } from '../api/agents'
import toast from 'react-hot-toast'

export default function Profile() {
  const { user, logout } = useAuth()
  const { roadmap, mastery } = useCLS()
  const navigate = useNavigate()
  const [deleting, setDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [regenerating, setRegenerating] = useState(false)

  const profile = (roadmap as any)?.profile ?? null
  const masteryEntries = Object.entries(mastery)
  const avgMastery = masteryEntries.length
    ? (masteryEntries.reduce((s, [, v]: any) => s + v.current_score, 0) / masteryEntries.length * 100).toFixed(0)
    : 0

  const handleRegenerate = async () => {
    if (!user) return
    setRegenerating(true)
    try {
      await roadmapApi.generateRoadmap(user.user_id)
      toast.success('Roadmap regenerated!')
      navigate('/dashboard')
    } catch {
      toast.error('Failed to regenerate roadmap')
    } finally {
      setRegenerating(false)
    }
  }

  const handleDelete = async () => {
    if (!user) return
    setDeleting(true)
    try {
      await userApi.deleteAccount(user.user_id)
      logout()
      navigate('/register')
      toast.success('Account deleted')
    } catch {
      toast.error('Failed to delete account')
      setDeleting(false)
    }
  }

  return (
    <div className="bg-animated min-h-screen p-4">
      <div className="max-w-xl mx-auto space-y-4 pt-8">
        <div className="flex items-center gap-3 mb-6">
          <Link to="/dashboard" className="p-2 rounded-lg hover:bg-white/5 transition-colors">
            <ArrowLeft className="w-4 h-4 text-slate-400" />
          </Link>
          <h1 className="text-xl font-bold text-slate-100">Profile & Settings</h1>
        </div>

        {/* User card */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass p-6 space-y-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
              <span className="text-2xl font-bold text-indigo-300">{user?.name?.[0]?.toUpperCase()}</span>
            </div>
            <div>
              <h2 className="font-bold text-slate-100 text-lg">{user?.name}</h2>
              <p className="text-sm text-slate-400">{user?.email}</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 pt-2">
            <div className="glass p-3 text-center">
              <p className="text-xl font-bold gradient-text">{avgMastery}%</p>
              <p className="text-xs text-slate-500">Avg Mastery</p>
            </div>
            <div className="glass p-3 text-center">
              <p className="text-xl font-bold gradient-text">
                {masteryEntries.filter(([,v]: any) => v.current_score >= 0.8).length}
              </p>
              <p className="text-xs text-slate-500">Mastered</p>
            </div>
            <div className="glass p-3 text-center">
              <p className="text-xl font-bold gradient-text">
                {(roadmap as any)?.weeks?.filter((w: any) => w.status === 'complete').length ?? 0}
              </p>
              <p className="text-xs text-slate-500">Weeks done</p>
            </div>
          </div>
        </motion.div>

        {/* Learning profile */}
        {profile && (
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
            className="glass p-6 space-y-3">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Brain className="w-4 h-4 text-indigo-400" />Learning Profile
            </h3>
            <div className="space-y-2">
              {[
                { icon: Target, label: 'Domain', value: profile.domain },
                { icon: Target, label: 'Goal', value: profile.goal },
                { icon: User, label: 'Level', value: profile.knowledge_level },
                { icon: Clock, label: 'Duration', value: `${profile.duration_weeks} weeks` },
              ].map(({ icon: Icon, label, value }) => (
                <div key={label} className="flex items-start gap-3 text-sm">
                  <Icon className="w-4 h-4 text-slate-500 mt-0.5 flex-shrink-0" />
                  <span className="text-slate-500 w-20 flex-shrink-0">{label}</span>
                  <span className="text-slate-200">{value}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Actions */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="glass p-6 space-y-3">
          <h3 className="text-sm font-semibold text-slate-200">Actions</h3>
          <button onClick={handleRegenerate} disabled={regenerating} className="btn-secondary w-full">
            {regenerating
              ? <div className="w-4 h-4 border border-slate-400/30 border-t-slate-400 rounded-full animate-spin" />
              : <><Save className="w-4 h-4" />Regenerate Roadmap</>}
          </button>
          <p className="text-xs text-slate-600">Regenerates your roadmap based on current mastery scores.</p>
        </motion.div>

        {/* Danger zone */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="glass border-rose-500/15 p-6 space-y-3">
          <h3 className="text-sm font-semibold text-rose-400">Danger Zone</h3>
          {!showDeleteConfirm ? (
            <button onClick={() => setShowDeleteConfirm(true)} className="btn-danger w-full">
              <Trash2 className="w-4 h-4" />Delete My Account
            </button>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-rose-300">This will permanently delete all your data. This cannot be undone.</p>
              <div className="flex gap-2">
                <button onClick={handleDelete} disabled={deleting} className="btn-danger flex-1">
                  {deleting ? <div className="w-4 h-4 border border-rose-400/30 border-t-rose-400 rounded-full animate-spin" /> : 'Yes, delete everything'}
                </button>
                <button onClick={() => setShowDeleteConfirm(false)} className="btn-secondary">Cancel</button>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}

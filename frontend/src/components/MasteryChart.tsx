import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

interface MasteryData { [topic: string]: { current_score: number; next_review?: string } }
interface Props { mastery: MasteryData }

const getColor = (score: number) => {
  if (score >= 0.8) return '#10B981'  // emerald — mastered
  if (score >= 0.5) return '#6366F1'  // indigo — in progress
  return '#F43F5E'                    // rose — needs review
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="glass-strong p-3 text-xs space-y-1">
      <p className="font-semibold text-slate-200">{d.topic}</p>
      <p className="text-slate-400">Mastery: <span className="text-white font-bold">{(d.score * 100).toFixed(0)}%</span></p>
      {d.next_review && (
        <p className="text-slate-500">Next review: {new Date(d.next_review).toLocaleDateString()}</p>
      )}
    </div>
  )
}

export default function MasteryChart({ mastery }: Props) {
  const data = Object.entries(mastery).map(([topic, v]) => ({
    topic: topic.length > 12 ? topic.slice(0, 12) + '…' : topic,
    fullTopic: topic,
    score: v.current_score,
    next_review: v.next_review,
  }))

  if (!data.length) return (
    <div className="glass p-6 text-center">
      <p className="text-sm text-slate-500">No mastery data yet — complete your first quiz</p>
    </div>
  )

  return (
    <div className="glass p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">Topic Mastery</h3>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />Mastered</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-indigo-500 inline-block" />Learning</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-500 inline-block" />Review</span>
        </div>
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 24, left: -20 }}>
            <XAxis dataKey="topic" tick={{ fill: '#64748B', fontSize: 10 }} angle={-30} textAnchor="end" interval={0} />
            <YAxis domain={[0, 1]} tick={{ fill: '#64748B', fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(99,102,241,0.05)' }} />
            <Bar dataKey="score" radius={[4, 4, 0, 0]}>
              {data.map((entry, i) => (
                <Cell key={i} fill={getColor(entry.score)} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </motion.div>
    </div>
  )
}

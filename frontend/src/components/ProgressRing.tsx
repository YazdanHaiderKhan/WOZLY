import { motion } from 'framer-motion'

interface Props { percent: number; size?: number; label?: string }

export default function ProgressRing({ percent, size = 100, label = 'Complete' }: Props) {
  const r = (size - 12) / 2
  const circ = 2 * Math.PI * r
  const offset = circ - (percent / 100) * circ

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke="rgba(99,102,241,0.1)" strokeWidth={8} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke="url(#ring-gradient)" strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: 'easeOut' }} />
        <defs>
          <linearGradient id="ring-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#6366F1" />
            <stop offset="100%" stopColor="#10B981" />
          </linearGradient>
        </defs>
      </svg>
      <div className="text-center -mt-2">
        <p className="text-2xl font-bold gradient-text">{Math.round(percent)}%</p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  )
}

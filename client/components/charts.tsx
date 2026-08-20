'use client'

import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from 'recharts'

const AXIS = '#a3a3a3'
const GRID = 'rgba(255,255,255,0.08)'
const PALETTE = ['#7b68ee', '#22c55e', '#f97316', '#38bdf8', '#a3a3a3']

const tooltipStyle = {
  background: '#191919',
  border: '1px solid rgba(255,255,255,0.12)',
  borderRadius: 8,
  color: '#f5f5f5',
  fontSize: 12,
}

export function ChartFrame({ children }: { children: React.ReactNode }) {
  return <div className="h-64 w-full min-w-0">{children}</div>
}

interface BarDatum {
  label: string
  value: number
}

export function SimpleBar({
  data,
  color = PALETTE[0],
  horizontal = false,
}: {
  data: BarDatum[]
  color?: string
  horizontal?: boolean
}) {
  if (horizontal) {
    return (
      <ChartFrame>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
            <XAxis type="number" stroke={AXIS} tick={{ fontSize: 11, fill: AXIS }} />
            <YAxis
              type="category"
              dataKey="label"
              width={110}
              stroke={AXIS}
              tick={{ fontSize: 11, fill: AXIS }}
            />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
            <Bar dataKey="value" fill={color} radius={[0, 4, 4, 0]} maxBarSize={22} />
          </BarChart>
        </ResponsiveContainer>
      </ChartFrame>
    )
  }
  return (
    <ChartFrame>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: 0, right: 8 }}>
          <XAxis
            dataKey="label"
            stroke={AXIS}
            tick={{ fontSize: 11, fill: AXIS }}
            interval={0}
            angle={-15}
            textAnchor="end"
            height={54}
          />
          <YAxis stroke={AXIS} tick={{ fontSize: 11, fill: AXIS }} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} maxBarSize={48} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

interface GroupedDatum {
  label: string
  [key: string]: string | number
}

export function GroupedBar({
  data,
  keys,
}: {
  data: GroupedDatum[]
  keys: { key: string; name: string; color: string }[]
}) {
  return (
    <ChartFrame>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: 0, right: 8 }}>
          <XAxis
            dataKey="label"
            stroke={AXIS}
            tick={{ fontSize: 11, fill: AXIS }}
            interval={0}
            angle={-15}
            textAnchor="end"
            height={54}
          />
          <YAxis stroke={AXIS} tick={{ fontSize: 11, fill: AXIS }} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <Legend wrapperStyle={{ fontSize: 12, color: AXIS }} />
          {keys.map((k) => (
            <Bar key={k.key} dataKey={k.key} name={k.name} fill={k.color} radius={[3, 3, 0, 0]} maxBarSize={28} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

export function SimplePie({ data }: { data: BarDatum[] }) {
  return (
    <ChartFrame>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            cx="50%"
            cy="50%"
            outerRadius={90}
            innerRadius={45}
            paddingAngle={2}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} stroke="#191919" />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12, color: AXIS }} />
        </PieChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

export { PALETTE }

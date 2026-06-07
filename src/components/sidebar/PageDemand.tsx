import type { Force } from "@/data/forces";
import { NATIONAL_AVG_IMD, CRIME_CATEGORIES } from "@/data/forces";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

const CRIME_COLORS = ["#22d3ee", "#10b981", "#fb7185", "#a78bfa", "#fbbf24", "#f97316", "#60a5fa"];

export function PageDemand({ force }: { force: Force }) {
  const hasImd = (["income", "health", "education", "housing"] as const).every((k) => force.imd[k] != null);
  const hasTopLsoas = force.topLsoas.length > 0;

  const radarData = (["income", "health", "education", "housing", "services"] as const).map((k) => ({
    domain: k.charAt(0).toUpperCase() + k.slice(1),
    Force: force.imd[k] ?? 0,
    National: NATIONAL_AVG_IMD[k] ?? 0,
  }));

  const lsoaData = force.topLsoas.map((l) => ({ name: l.name.slice(-7), ...l.scores }));

  return (
    <div className="p-4 space-y-4">
      <Section title="Modeling Methodology">
        <p className="text-xs text-muted-foreground leading-relaxed border border-border-strong p-3 bg-background/40">
          Spatial Random Forest demand prediction over Cambridge Crime Harm Index (CHI) weights,
          stratified by IMD sub-domain rank and historical call volume. Outputs feed the LP optimizer
          downstream as per-LSOA demand pressure coefficients.
        </p>
      </Section>

      <Section title="Deprivation Profile · IMD vs National Average">
        {!hasImd ? (
          <Missing
            title="IMD force profile unavailable in current cache"
            body="Backend full recompute can aggregate IoD2019 LSOA scores to force level. Current generated cache is from existing reports only, which did not serialize those rows."
          />
        ) : (
          <div className="border border-border-strong bg-background/40 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} outerRadius="72%">
                <PolarGrid stroke="#3f3f46" />
                <PolarAngleAxis dataKey="domain" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
                <PolarRadiusAxis tick={{ fill: "#52525b", fontSize: 9 }} stroke="#3f3f46" />
                <Radar dataKey="National" stroke="#52525b" fill="#52525b" fillOpacity={0.15} />
                <Radar dataKey="Force" stroke="#22d3ee" fill="#22d3ee" fillOpacity={0.35} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Section>

      <Section title="Micro-Level Analysis · LSOA Layer">
        <Missing
          title="No real LSOA heatmap implemented yet"
          body="Research files contain raw LSOA-linked crime records, but no backend cache or endpoint yet exposes LSOA demand polygons or deployment cells. Simulated heatmap removed."
        />
      </Section>

      <Section title="Top 10 High-Demand LSOAs">
        {!hasTopLsoas ? (
          <Missing
            title="Top LSOAs unavailable in current cache"
            body="Existing audits do not save top LSOA rows. Backend full recompute can derive them from LSOA crime records, but current cache does not fake them."
          />
        ) : (
          <div className="border border-border-strong bg-background/40 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={lsoaData} margin={{ top: 10, right: 10, left: -20, bottom: 30 }}>
                <XAxis
                  dataKey="name"
                  tick={{ fill: "#a1a1aa", fontSize: 9 }}
                  angle={-35}
                  textAnchor="end"
                  interval={0}
                  stroke="#3f3f46"
                />
                <YAxis tick={{ fill: "#a1a1aa", fontSize: 9 }} stroke="#3f3f46" />
                <Tooltip
                  contentStyle={{
                    background: "#18181b",
                    border: "1px solid #3f3f46",
                    fontSize: 11,
                    fontFamily: "JetBrains Mono",
                  }}
                />
                {CRIME_CATEGORIES.map((c, i) => (
                  <Bar key={c} dataKey={c} stackId="a" fill={CRIME_COLORS[i % CRIME_COLORS.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-muted-foreground mb-2">
        {title}
      </div>
      {children}
    </div>
  );
}

function Missing({ title, body }: { title: string; body: string }) {
  return (
    <div className="border border-border-strong bg-background/40 p-3">
      <div className="font-mono text-[10px] tracking-wider uppercase text-muted-foreground">{title}</div>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{body}</p>
    </div>
  );
}

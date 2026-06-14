import { useEffect, useMemo, useState } from 'react';
import api from '../api/client';
import type {
  CapabilityDomainSummary,
  ControlCenterResponse,
  InstalledAgentSummary,
} from '../types';

function MetricCard({
  label,
  value,
  hint,
  tone = 'default',
}: {
  label: string;
  value: string | number;
  hint: string;
  tone?: 'default' | 'success' | 'warning';
}) {
  const toneClasses = {
    default: 'border-slate-700 text-white',
    success: 'border-emerald-500/40 text-emerald-300',
    warning: 'border-amber-500/40 text-amber-300',
  };

  return (
    <div className={`rounded-2xl border bg-slate-900/70 p-5 ${toneClasses[tone]}`}>
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
      <p className="mt-2 text-sm text-slate-500">{hint}</p>
    </div>
  );
}

function DomainCard({ domain }: { domain: CapabilityDomainSummary }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 hover:border-cyan-500/40 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-2xl">{domain.icon}</p>
          <h3 className="mt-3 text-lg font-semibold text-white">{domain.name}</h3>
        </div>
        <div className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">
          {domain.skills} skills
        </div>
      </div>
      <p className="mt-3 text-sm text-slate-400">
        {domain.tools} tools exposed across this capability domain.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {domain.highlights.map((highlight) => (
          <span
            key={highlight}
            className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300"
          >
            {highlight}
          </span>
        ))}
      </div>
    </div>
  );
}

function AgentCard({ agent }: { agent: InstalledAgentSummary }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{agent.name}</h3>
          <p className="text-sm text-slate-400">{agent.kind}</p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs ${
            agent.network_access
              ? 'bg-amber-500/15 text-amber-300'
              : 'bg-emerald-500/15 text-emerald-300'
          }`}
        >
          {agent.network_access ? 'networked' : 'local-only'}
        </span>
      </div>
      <p className="mt-3 text-sm text-slate-300">{agent.description}</p>
      <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
        <div>
          <p className="text-slate-500">Tasks</p>
          <p className="text-white">{agent.task_count}</p>
        </div>
        <div>
          <p className="text-slate-500">Completed</p>
          <p className="text-white">{agent.completed}</p>
        </div>
        <div>
          <p className="text-slate-500">Skills</p>
          <p className="text-white">{agent.skills}</p>
        </div>
      </div>
    </div>
  );
}

const quickStarts = [
  {
    title: 'Private Research',
    description: 'Read local docs, PDFs, and notes without sending them outside your machine.',
    route: '/chat',
    cta: 'Open Chat',
  },
  {
    title: 'Agent Queue',
    description: 'Submit jobs, reprioritize them, and let workers drain the queue like a local scheduler.',
    route: '/logs',
    cta: 'Inspect Runtime',
  },
  {
    title: 'Capability Explorer',
    description: 'Browse the full surface area of R by domain, tools, and concrete skill names.',
    route: '/skills',
    cta: 'Explore Skills',
  },
];

export default function Dashboard() {
  const [overview, setOverview] = useState<ControlCenterResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchOverview() {
      try {
        const data = await api.getControlCenter();
        setOverview(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch control center');
      } finally {
        setLoading(false);
      }
    }

    fetchOverview();
    const interval = setInterval(fetchOverview, 10000);
    return () => clearInterval(interval);
  }, []);

  const totalTools = useMemo(
    () => overview?.capability_domains.reduce((sum, domain) => sum + domain.tools, 0) ?? 0,
    [overview]
  );

  const queueDepth = useMemo(() => {
    if (!overview) {
      return 0;
    }
    const tasks = overview.agent_os.tasks;
    return tasks.queued + tasks.running + tasks.paused;
  }, [overview]);

  if (loading) {
    return (
      <div className="flex h-80 items-center justify-center">
        <div className="text-slate-400">Loading control center...</div>
      </div>
    );
  }

  if (error || !overview) {
    return (
      <div className="rounded-2xl border border-red-500/40 bg-red-950/20 p-6">
        <h1 className="text-2xl font-semibold text-red-300">Control Center unavailable</h1>
        <p className="mt-2 text-slate-300">{error || 'No overview data returned.'}</p>
        <p className="mt-3 text-sm text-slate-500">
          Start the API with <code>r serve</code> and make sure the local LLM is reachable.
        </p>
      </div>
    );
  }

  const llmHealthy = overview.status.llm.connected;
  const tasks = overview.agent_os.tasks;

  return (
    <div className="space-y-8">
      <section className="rounded-3xl border border-cyan-500/20 bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.15),_transparent_40%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.96))] p-8">
        <div className="flex flex-col gap-8 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-cyan-200">
              Agent OS Control Center
            </div>
            <h1 className="mt-5 text-4xl font-semibold tracking-tight text-white md:text-5xl">
              A local command center for private AI agents.
            </h1>
            <p className="mt-4 text-lg leading-8 text-slate-300">
              R is more than chat. It is a runtime for local agents, governed tools, memory,
              workflows, and queues. This view is designed to show that whole surface area at once.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4 xl:min-w-[420px]">
            <MetricCard
              label="LLM Runtime"
              value={llmHealthy ? 'Online' : 'Offline'}
              hint={overview.status.llm.model || 'No active model'}
              tone={llmHealthy ? 'success' : 'warning'}
            />
            <MetricCard
              label="Agent Queue"
              value={queueDepth}
              hint={`${tasks.queued} queued • ${tasks.running} running`}
              tone={queueDepth > 0 ? 'warning' : 'default'}
            />
            <MetricCard
              label="Capabilities"
              value={overview.status.skills_loaded}
              hint={`${totalTools} callable tools`}
            />
            <MetricCard
              label="Installed Agents"
              value={overview.agent_os.agents}
              hint={`${overview.agent_os.events} lifecycle events recorded`}
            />
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Completed Tasks"
          value={tasks.completed}
          hint="Finished in the local Agent OS runtime"
          tone="success"
        />
        <MetricCard
          label="Failed Tasks"
          value={tasks.failed}
          hint="Retry and recovery surface to improve next"
          tone={tasks.failed > 0 ? 'warning' : 'default'}
        />
        <MetricCard
          label="Memory"
          value={overview.memory.provider}
          hint={overview.memory.continuous ? 'Continuous recall enabled' : 'Local session memory'}
        />
        <MetricCard
          label="Security"
          value={overview.security.local_only ? 'Local-first' : 'Mixed'}
          hint={`${overview.security.mode} approvals • audit ${overview.security.audit_enabled ? 'on' : 'off'}`}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-2xl font-semibold text-white">What R Can Do</h2>
              <p className="mt-2 text-sm text-slate-400">
                Capability domains make the product legible before the user learns commands.
              </p>
            </div>
            <a
              href="#/skills"
              className="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:border-cyan-400 hover:text-white"
            >
              Open Explorer
            </a>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {overview.capability_domains.map((domain) => (
              <DomainCard key={domain.name} domain={domain} />
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6">
            <h2 className="text-2xl font-semibold text-white">Operator Surfaces</h2>
            <div className="mt-5 space-y-3">
              {quickStarts.map((item) => (
                <a
                  key={item.title}
                  href={`#${item.route}`}
                  className="block rounded-2xl border border-slate-800 bg-slate-900/80 p-4 hover:border-cyan-500/40"
                >
                  <div className="flex items-center justify-between gap-4">
                    <h3 className="text-base font-semibold text-white">{item.title}</h3>
                    <span className="text-sm text-cyan-300">{item.cta}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-400">{item.description}</p>
                </a>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6">
            <h2 className="text-2xl font-semibold text-white">Security Posture</h2>
            <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-2xl bg-slate-900/80 p-4">
                <p className="text-slate-500">Mode</p>
                <p className="mt-2 text-white">{overview.security.mode}</p>
              </div>
              <div className="rounded-2xl bg-slate-900/80 p-4">
                <p className="text-slate-500">Network</p>
                <p className="mt-2 text-white">
                  {overview.security.network_access ? 'enabled' : 'blocked by default'}
                </p>
              </div>
              <div className="rounded-2xl bg-slate-900/80 p-4">
                <p className="text-slate-500">Local LLM</p>
                <p className="mt-2 text-white">{overview.security.local_only ? 'required' : 'optional'}</p>
              </div>
              <div className="rounded-2xl bg-slate-900/80 p-4">
                <p className="text-slate-500">Filesystem Roots</p>
                <p className="mt-2 text-white">
                  {overview.security.filesystem_roots_enforced ? 'enforced' : 'open'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold text-white">Installed Agents</h2>
            <p className="mt-2 text-sm text-slate-400">
              Local identities with isolated capabilities, memory namespaces, and queue history.
            </p>
          </div>
          <a
            href="#/settings"
            className="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:border-cyan-400 hover:text-white"
          >
            Runtime Settings
          </a>
        </div>

        {overview.installed_agents.length === 0 ? (
          <div className="mt-6 rounded-2xl border border-dashed border-slate-700 p-8 text-center text-slate-400">
            No installed agents yet. Use <code>r os agent install</code> to create the first local operator.
          </div>
        ) : (
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {overview.installed_agents.map((agent) => (
              <AgentCard key={agent.name} agent={agent} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

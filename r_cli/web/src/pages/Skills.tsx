import { useEffect, useState } from 'react';
import api from '../api/client';
import type { SkillInfo } from '../types';

const categoryIcons: Record<string, string> = {
  'Knowledge & Docs': '📚',
  'Code & Data': '💻',
  'Automation & OS': '⚙️',
  'Web & Network': '🌐',
  'Media & Voice': '🎙️',
  Communication: '📨',
  'Agent Systems': '🧠',
  Utilities: '🛠️',
  default: '🛠️',
};

function SkillCard({ skill, onClick }: { skill: SkillInfo; onClick: () => void }) {
  const icon = categoryIcons[skill.category] || categoryIcons.default;

  return (
    <div
      onClick={onClick}
      className="bg-slate-800 rounded-lg p-4 border border-slate-700 hover:border-blue-500 cursor-pointer transition-colors"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl">{icon}</span>
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-white">{skill.name}</h3>
          <p className="text-slate-400 text-sm mt-1 line-clamp-2">{skill.description}</p>
          <div className="flex items-center gap-2 mt-2">
            <span className="px-2 py-0.5 bg-slate-700 rounded text-xs text-slate-300">
              {skill.category}
            </span>
            <span className="text-xs text-slate-500">
              {skill.tools.length} tools
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function SkillDetail({ skill, onClose }: { skill: SkillInfo; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-slate-800 rounded-lg border border-slate-700 max-w-2xl w-full max-h-[80vh] overflow-hidden">
        <div className="p-6 border-b border-slate-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">
              {categoryIcons[skill.category] || categoryIcons.default}
            </span>
            <div>
              <h2 className="text-xl font-bold text-white">{skill.name}</h2>
              <p className="text-slate-400 text-sm">{skill.category}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-2xl"
          >
            ×
          </button>
        </div>

        <div className="p-6 overflow-y-auto max-h-[60vh]">
          <p className="text-slate-300 mb-6">{skill.description}</p>

          <h3 className="font-bold text-white mb-3">Available Tools ({skill.tools.length})</h3>
          <div className="space-y-3">
            {skill.tools.map((tool) => (
              <div key={tool.name} className="bg-slate-700/50 rounded-lg p-4">
                <h4 className="font-medium text-white">{tool.name}</h4>
                <p className="text-slate-400 text-sm mt-1">{tool.description}</p>
                {tool.parameters && Object.keys(tool.parameters).length > 0 && (
                  <details className="mt-2">
                    <summary className="text-xs text-slate-500 cursor-pointer">
                      Parameters
                    </summary>
                    <pre className="mt-2 p-2 bg-slate-900 rounded text-xs text-slate-300 overflow-x-auto">
                      {JSON.stringify(tool.parameters, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Skills() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<SkillInfo | null>(null);
  const [filter, setFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSkills() {
      try {
        const response = await api.getSkills();
        setSkills(response.skills);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch skills');
      } finally {
        setLoading(false);
      }
    }

    fetchSkills();
  }, []);

  const categories = [...new Set(skills.map((s) => s.category))];

  const filteredSkills = skills.filter((skill) => {
    const matchesSearch =
      skill.name.toLowerCase().includes(filter.toLowerCase()) ||
      skill.description.toLowerCase().includes(filter.toLowerCase());
    const matchesCategory = !categoryFilter || skill.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading skills...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-500 rounded-lg p-6">
        <h2 className="text-red-400 font-bold mb-2">Error</h2>
        <p className="text-slate-300">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Skills</h1>
        <span className="text-slate-400">{skills.length} skills available</span>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <input
          type="text"
          placeholder="Search skills..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
        />
        <select
          value={categoryFilter || ''}
          onChange={(e) => setCategoryFilter(e.target.value || null)}
          className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>
      </div>

      {/* Skills Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredSkills.map((skill) => (
          <SkillCard
            key={skill.name}
            skill={skill}
            onClick={() => setSelectedSkill(skill)}
          />
        ))}
      </div>

      {filteredSkills.length === 0 && (
        <div className="text-center py-12 text-slate-400">
          No skills found matching your criteria.
        </div>
      )}

      {/* Skill Detail Modal */}
      {selectedSkill && (
        <SkillDetail skill={selectedSkill} onClose={() => setSelectedSkill(null)} />
      )}
    </div>
  );
}

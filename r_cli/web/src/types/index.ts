// API Types for R CLI Dashboard

export interface LLMStatus {
  connected: boolean;
  backend: string | null;
  model: string | null;
  base_url: string | null;
}

export interface StatusResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  uptime_seconds: number;
  llm: LLMStatus;
  skills_loaded: number;
  timestamp: string;
}

export interface AgentTaskSummary {
  queued: number;
  paused: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
}

export interface AgentOSStatus {
  database: string;
  agents: number;
  events: number;
  tasks: AgentTaskSummary;
}

export interface InstalledAgentSummary {
  name: string;
  description: string;
  kind: string;
  task_count: number;
  completed: number;
  skills: number;
  network_access: boolean;
}

export interface CapabilityDomainSummary {
  name: string;
  icon: string;
  skills: number;
  tools: number;
  highlights: string[];
}

export interface MemoryOverview {
  provider: string;
  continuous: boolean;
}

export interface SecurityOverview {
  mode: string;
  local_only: boolean;
  network_access: boolean;
  audit_enabled: boolean;
  filesystem_roots_enforced: boolean;
}

export interface ControlCenterResponse {
  status: StatusResponse;
  agent_os: AgentOSStatus;
  installed_agents: InstalledAgentSummary[];
  capability_domains: CapabilityDomainSummary[];
  memory: MemoryOverview;
  security: SecurityOverview;
}

export interface SkillTool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface SkillInfo {
  name: string;
  description: string;
  category: string;
  tools: SkillTool[];
}

export interface SkillsResponse {
  skills: SkillInfo[];
  total: number;
}

// OpenAI-compatible chat format
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  model?: string;
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
  tools_enabled?: boolean;
}

export interface ChatChoice {
  index: number;
  message: ChatMessage;
  finish_reason: string | null;
}

export interface ChatUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatChoice[];
  usage?: ChatUsage;
}

// Simple chat format (convenience wrapper)
export interface SimpleChatRequest {
  message: string;
  skill?: string;
  stream?: boolean;
}

export interface SimpleChatResponse {
  response: string;
  skill_used: string | null;
  tools_called: string[];
  tokens_used: number;
}

export interface AuditEvent {
  timestamp: string;
  action: string;
  severity: string;
  user_id: string | null;
  username: string | null;
  auth_type: string | null;
  client_ip: string | null;
  resource: string | null;
  success: boolean;
  error_message: string | null;
  duration_ms: number | null;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthUser {
  user_id: string;
  username: string;
  scopes: string[];
  auth_type: string;
}

export interface APIKeyInfo {
  key_id: string;
  name: string;
  scopes: string[];
  created_at: string;
  last_used: string | null;
  expires_at: string | null;
  is_active: boolean;
}

export interface APIKeyCreateResponse {
  key: string;
  key_id: string;
  name: string;
  scopes: string[];
  message: string;
}

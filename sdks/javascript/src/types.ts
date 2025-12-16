/**
 * Type definitions for R CLI SDK
 */

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
}

export interface ChatResponse {
  message: string;
  skill_used?: string;
  tools_called?: ToolCall[];
  model?: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface SkillInfo {
  name: string;
  description: string;
  version: string;
  category: string;
  enabled: boolean;
  tools: ToolInfo[];
}

export interface LLMStatus {
  connected: boolean;
  provider?: string;
  model?: string;
  base_url?: string;
}

export interface StatusResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  uptime_seconds: number;
  llm: LLMStatus;
  skills_loaded: number;
  timestamp: string;
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
  last_used?: string;
}

export interface APIKeyCreateResponse extends APIKeyInfo {
  key: string;
}

export interface AuditEvent {
  timestamp: string;
  action: string;
  severity: string;
  success: boolean;
  username?: string;
  resource?: string;
  client_ip?: string;
  auth_type?: string;
  duration_ms?: number;
  error_message?: string;
}

export interface RClientOptions {
  baseUrl?: string;
  apiKey?: string;
  token?: string;
  timeout?: number;
}

export interface ChatOptions {
  history?: ChatMessage[];
  skill?: string;
  stream?: boolean;
}

export interface AuditLogsOptions {
  limit?: number;
  action?: string;
  success?: boolean;
}

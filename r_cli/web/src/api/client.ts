// R CLI API Client

import type {
  StatusResponse,
  ControlCenterResponse,
  SkillsResponse,
  SkillInfo,
  ChatRequest,
  ChatResponse,
  AuditEvent,
  Token,
  AuthUser,
  APIKeyInfo,
  APIKeyCreateResponse,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class APIClient {
  private token: string | null = null;

  constructor() {
    // Load token from localStorage
    this.token = localStorage.getItem('r_cli_token');
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Auth
  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('r_cli_token', token);
    } else {
      localStorage.removeItem('r_cli_token');
    }
  }

  async login(username: string, password: string): Promise<Token> {
    const token = await this.request<Token>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    this.setToken(token.access_token);
    return token;
  }

  async logout() {
    this.setToken(null);
  }

  async getMe(): Promise<AuthUser> {
    return this.request<AuthUser>('/auth/me');
  }

  // Status
  async getStatus(): Promise<StatusResponse> {
    return this.request<StatusResponse>('/v1/status');
  }

  async getControlCenter(): Promise<ControlCenterResponse> {
    return this.request<ControlCenterResponse>('/v1/control-center');
  }

  async getHealth(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/health');
  }

  // Skills
  async getSkills(): Promise<SkillsResponse> {
    return this.request<SkillsResponse>('/v1/skills');
  }

  async getSkill(name: string): Promise<SkillInfo> {
    return this.request<SkillInfo>(`/v1/skills/${name}`);
  }

  async callSkillTool(
    skillName: string,
    toolName: string,
    args: Record<string, unknown>
  ): Promise<unknown> {
    return this.request(`/v1/skills/${skillName}/tools/${toolName}`, {
      method: 'POST',
      body: JSON.stringify(args),
    });
  }

  // Chat (OpenAI-compatible format)
  async chat(request: { message: string }): Promise<{ response: string; skill_used?: string; tools_called?: string[] }> {
    // Convert simple message to OpenAI format
    const openaiRequest: ChatRequest = {
      messages: [{ role: 'user', content: request.message }],
    };

    const response = await this.request<ChatResponse>('/v1/chat', {
      method: 'POST',
      body: JSON.stringify(openaiRequest),
    });

    // Extract response from OpenAI format
    const assistantMessage = response.choices?.[0]?.message?.content || '';

    return {
      response: assistantMessage,
      skill_used: undefined, // Not available in OpenAI format
      tools_called: [],
    };
  }

  // Audit Logs
  async getAuditLogs(params?: {
    limit?: number;
    action?: string;
    success?: boolean;
  }): Promise<AuditEvent[]> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.action) searchParams.set('action', params.action);
    if (params?.success !== undefined) searchParams.set('success', params.success.toString());

    const query = searchParams.toString();
    return this.request<AuditEvent[]>(`/v1/audit/logs${query ? `?${query}` : ''}`);
  }

  // API Keys
  async getAPIKeys(): Promise<APIKeyInfo[]> {
    return this.request<APIKeyInfo[]>('/auth/api-keys');
  }

  async createAPIKey(
    name: string,
    scopes: string[],
    expiresInDays?: number
  ): Promise<APIKeyCreateResponse> {
    return this.request<APIKeyCreateResponse>('/auth/api-keys', {
      method: 'POST',
      body: JSON.stringify({ name, scopes, expires_in_days: expiresInDays }),
    });
  }

  async deleteAPIKey(keyId: string): Promise<void> {
    await this.request(`/auth/api-keys/${keyId}`, {
      method: 'DELETE',
    });
  }

  // Users (admin)
  async createUser(
    username: string,
    password: string,
    scopes: string[]
  ): Promise<{ user_id: string; username: string }> {
    return this.request('/auth/users', {
      method: 'POST',
      body: JSON.stringify({ username, password, scopes }),
    });
  }
}

export const api = new APIClient();
export default api;

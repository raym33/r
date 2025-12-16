/**
 * R CLI API Client
 */

import type {
  RClientOptions,
  ChatMessage,
  ChatResponse,
  ChatOptions,
  SkillInfo,
  StatusResponse,
  AuthUser,
  APIKeyInfo,
  APIKeyCreateResponse,
  AuditEvent,
  AuditLogsOptions,
} from './types';
import { AuthError, RateLimitError, APIError } from './errors';

export class RClient {
  private baseUrl: string;
  private apiKey?: string;
  private token?: string;
  private timeout: number;

  constructor(options: RClientOptions = {}) {
    this.baseUrl = (options.baseUrl || 'http://localhost:8000').replace(/\/$/, '');
    this.apiKey = options.apiKey;
    this.token = options.token;
    this.timeout = options.timeout || 30000;
  }

  private headers(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    } else if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (response.status === 401) {
      throw new AuthError('Authentication required', 401);
    }
    if (response.status === 403) {
      throw new AuthError('Permission denied', 403);
    }
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After');
      throw new RateLimitError(
        'Rate limit exceeded',
        retryAfter ? parseFloat(retryAfter) : undefined
      );
    }
    if (!response.ok) {
      let detail: string;
      try {
        const data = await response.json();
        detail = data.detail || response.statusText;
      } catch {
        detail = response.statusText;
      }
      throw new APIError(detail, response.status);
    }
    return response.json();
  }

  private async fetch<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        headers: { ...this.headers(), ...options.headers },
        signal: controller.signal,
      });
      return this.handleResponse<T>(response);
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // Auth methods

  async login(username: string, password: string): Promise<string> {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${this.baseUrl}/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });

    const data = await this.handleResponse<{ access_token: string }>(response);
    this.token = data.access_token;
    return this.token;
  }

  logout(): void {
    this.token = undefined;
  }

  async getMe(): Promise<AuthUser> {
    return this.fetch<AuthUser>('/auth/me');
  }

  // Status methods

  async health(): Promise<{ status: string }> {
    return this.fetch<{ status: string }>('/health');
  }

  async status(): Promise<StatusResponse> {
    return this.fetch<StatusResponse>('/v1/status');
  }

  // Skills methods

  async listSkills(): Promise<SkillInfo[]> {
    return this.fetch<SkillInfo[]>('/v1/skills');
  }

  async getSkill(name: string): Promise<SkillInfo> {
    return this.fetch<SkillInfo>(`/v1/skills/${encodeURIComponent(name)}`);
  }

  // Chat methods

  async chat(message: string, options: ChatOptions = {}): Promise<ChatResponse> {
    const messages: ChatMessage[] = [];

    if (options.history) {
      messages.push(...options.history);
    }
    messages.push({ role: 'user', content: message });

    const payload: Record<string, unknown> = { messages };
    if (options.skill) {
      payload.skill = options.skill;
    }

    return this.fetch<ChatResponse>('/v1/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async *chatStream(
    message: string,
    options: Omit<ChatOptions, 'stream'> = {}
  ): AsyncGenerator<string, void, unknown> {
    const messages: ChatMessage[] = [];

    if (options.history) {
      messages.push(...options.history);
    }
    messages.push({ role: 'user', content: message });

    const payload: Record<string, unknown> = {
      messages,
      stream: true,
    };
    if (options.skill) {
      payload.skill = options.skill;
    }

    const response = await fetch(`${this.baseUrl}/v1/chat`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      await this.handleResponse(response);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new APIError('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data !== '[DONE]') {
              yield data;
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  // API Keys methods

  async listAPIKeys(): Promise<APIKeyInfo[]> {
    return this.fetch<APIKeyInfo[]>('/auth/api-keys');
  }

  async createAPIKey(
    name: string,
    scopes?: string[]
  ): Promise<APIKeyCreateResponse> {
    const params = new URLSearchParams({ name });
    if (scopes) {
      scopes.forEach(scope => params.append('scopes', scope));
    }

    return this.fetch<APIKeyCreateResponse>(
      `/auth/api-keys?${params.toString()}`,
      { method: 'POST' }
    );
  }

  async deleteAPIKey(keyId: string): Promise<void> {
    await this.fetch<{ message: string }>(
      `/auth/api-keys/${encodeURIComponent(keyId)}`,
      { method: 'DELETE' }
    );
  }

  // Audit logs

  async getAuditLogs(options: AuditLogsOptions = {}): Promise<AuditEvent[]> {
    const params = new URLSearchParams();
    if (options.limit) {
      params.append('limit', options.limit.toString());
    }
    if (options.action) {
      params.append('action', options.action);
    }
    if (options.success !== undefined) {
      params.append('success', options.success.toString());
    }

    const query = params.toString();
    return this.fetch<AuditEvent[]>(
      `/v1/audit/logs${query ? `?${query}` : ''}`
    );
  }
}

# R SDK for JavaScript/TypeScript

Official JavaScript/TypeScript SDK for the R CLI API - Your Local AI Agent Runtime.

## Installation

```bash
npm install r-sdk
# or
yarn add r-sdk
# or
pnpm add r-sdk
```

## Quick Start

```typescript
import { RClient } from 'r-sdk';

// Connect to local R CLI server
const client = new RClient({ baseUrl: 'http://localhost:8000' });

// Check server status
const status = await client.status();
console.log(`Server: ${status.status}, Skills: ${status.skills_loaded}`);

// Chat with AI
const response = await client.chat('Generate a TypeScript hello world');
console.log(response.message);
```

## Authentication

### API Key (Recommended)
```typescript
const client = new RClient({
  baseUrl: 'http://localhost:8000',
  apiKey: 'your-api-key'
});
```

### Username/Password
```typescript
const client = new RClient({ baseUrl: 'http://localhost:8000' });
await client.login('admin', 'password');
```

### JWT Token
```typescript
const client = new RClient({
  baseUrl: 'http://localhost:8000',
  token: 'your-jwt-token'
});
```

## Usage Examples

### Chat

```typescript
import { RClient, ChatMessage } from 'r-sdk';

const client = new RClient({ apiKey: 'your-key' });

// Simple chat
const response = await client.chat('What is 2 + 2?');
console.log(response.message);

// With conversation history
const history: ChatMessage[] = [
  { role: 'user', content: 'My name is Alice' },
  { role: 'assistant', content: 'Hello Alice!' },
];
const response2 = await client.chat("What's my name?", { history });

// Force a specific skill
const response3 = await client.chat('Generate SQL query', { skill: 'sql' });
console.log(`Used skill: ${response3.skill_used}`);
console.log(`Tools called: ${response3.tools_called}`);

// Streaming
for await (const chunk of client.chatStream('Write a poem')) {
  process.stdout.write(chunk);
}
```

### Skills

```typescript
// List all skills
const skills = await client.listSkills();
for (const skill of skills) {
  console.log(`${skill.name}: ${skill.description}`);
  for (const tool of skill.tools) {
    console.log(`  - ${tool.name}`);
  }
}

// Get specific skill
const skill = await client.getSkill('code');
console.log(skill.description);
```

### API Keys Management

```typescript
// List your API keys
const keys = await client.listAPIKeys();
for (const key of keys) {
  console.log(`${key.name} - ${key.scopes.join(', ')}`);
}

// Create new API key
const newKey = await client.createAPIKey('My App', ['read', 'write', 'chat']);
console.log(`Save this key: ${newKey.key}`);  // Only shown once!

// Delete an API key
await client.deleteAPIKey(newKey.key_id);
```

### Audit Logs (Admin)

```typescript
// Get recent audit logs
const logs = await client.getAuditLogs({ limit: 100 });
for (const log of logs) {
  console.log(`[${log.severity}] ${log.action}: ${log.success}`);
}

// Filter by action
const chatLogs = await client.getAuditLogs({ action: 'chat.request' });

// Filter by success/failure
const failures = await client.getAuditLogs({ success: false });
```

## Error Handling

```typescript
import { RClient, AuthError, RateLimitError, APIError } from 'r-sdk';

const client = new RClient();

try {
  const response = await client.chat('Hello');
} catch (error) {
  if (error instanceof AuthError) {
    console.log(`Auth failed: ${error.message}`);
  } else if (error instanceof RateLimitError) {
    console.log(`Rate limited. Retry after: ${error.retryAfter}s`);
  } else if (error instanceof APIError) {
    console.log(`API error ${error.statusCode}: ${error.message}`);
  }
}
```

## TypeScript Support

Full TypeScript support with exported types:

```typescript
import type {
  ChatMessage,
  ChatResponse,
  SkillInfo,
  StatusResponse,
  AuthUser,
  APIKeyInfo,
  AuditEvent,
  RClientOptions,
} from 'r-sdk';

const options: RClientOptions = {
  baseUrl: 'http://localhost:8000',
  apiKey: 'your-key',
  timeout: 60000,
};

const client = new RClient(options);
const status: StatusResponse = await client.status();
const response: ChatResponse = await client.chat('Hi');
const skills: SkillInfo[] = await client.listSkills();
```

## Browser Usage

The SDK works in browsers with fetch support:

```html
<script type="module">
  import { RClient } from 'https://unpkg.com/r-sdk/dist/index.mjs';

  const client = new RClient({ apiKey: 'your-key' });
  const response = await client.chat('Hello!');
  console.log(response.message);
</script>
```

## Node.js Usage

Works with Node.js 18+ (native fetch):

```javascript
const { RClient } = require('r-sdk');

const client = new RClient({ apiKey: 'your-key' });
client.chat('Hello!').then(response => {
  console.log(response.message);
});
```

## License

MIT

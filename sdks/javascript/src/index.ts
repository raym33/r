/**
 * R CLI JavaScript/TypeScript SDK
 *
 * @example
 * ```typescript
 * import { RClient } from 'r-sdk';
 *
 * const client = new RClient({ apiKey: 'your-key' });
 * const response = await client.chat('Hello!');
 * console.log(response.message);
 * ```
 */

export { RClient } from './client';
export * from './types';
export * from './errors';

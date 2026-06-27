/**
 * Layer 3 — MCP Registry.
 *
 * The "smart phone book" of security-tool MCP servers. Maps a tool name to its
 * MCP server image, transport, install method and trust tier. The router queries
 * this first; only tools NOT found here fall through to terminal automation (L4).
 *
 * Whitelist-only: a tool not present in the registry is never auto-executed via
 * MCP — it is blocked or handled by L4, never silently trusted.
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { createLogger } from '../util/logger.js';

const log = createLogger('mcp-registry');

export type Transport = 'stdio' | 'sse' | 'http';
export type TrustTier = 'official' | 'community' | 'experimental';

export interface ToolSchema {
  name: string;
  inputSchema?: Record<string, unknown>;
  outputSchema?: Record<string, unknown>;
}

export interface RegistryEntry {
  mcpServer: string;
  transport: Transport;
  install?: { docker?: string; native?: string };
  trustTier: TrustTier;
  sha256?: string;
  toolSchemas?: ToolSchema[];
}

export interface RegistryManifest {
  schemaVersion: string;
  lastUpdated: string;
  tools: Record<string, RegistryEntry>;
}

/** Seed registry shipped with the platform; refreshed from a hosted manifest. */
export const SEED_MANIFEST: RegistryManifest = {
  schemaVersion: '2',
  lastUpdated: '2026-06-26T00:00:00Z',
  tools: {
    nuclei: {
      mcpServer: 'ghcr.io/projectdiscovery/nuclei-mcp:latest',
      transport: 'stdio',
      install: { native: 'pip install nuclei-cli' },
      trustTier: 'official',
      toolSchemas: [{ name: 'scan' }],
    },
    ghidra: {
      mcpServer: 'github:bethington/ghidra-mcp@v2.1',
      transport: 'stdio',
      trustTier: 'community',
      toolSchemas: [{ name: 'analyze' }],
    },
    nmap: {
      mcpServer: 'ghcr.io/org/nmap-mcp:latest',
      transport: 'stdio',
      install: { native: 'apt install nmap' },
      trustTier: 'community',
      toolSchemas: [{ name: 'scan' }],
    },
  },
};

export class McpRegistry {
  private manifest: RegistryManifest;

  constructor(manifest: RegistryManifest = SEED_MANIFEST) {
    this.manifest = manifest;
  }

  static load(path: string): McpRegistry {
    const abs = resolve(process.cwd(), path);
    if (!existsSync(abs)) {
      log.warn(`registry not found at ${path}, using seed manifest`);
      return new McpRegistry();
    }
    try {
      const manifest = JSON.parse(readFileSync(abs, 'utf8')) as RegistryManifest;
      log.info(`loaded registry v${manifest.schemaVersion} (${Object.keys(manifest.tools).length} tools)`);
      return new McpRegistry(manifest);
    } catch (err) {
      log.error('failed to parse registry, using seed', String(err));
      return new McpRegistry();
    }
  }

  /** Normalize a tool name: lowercase, strip version suffixes. */
  static normalize(tool: string): string {
    return tool.toLowerCase().replace(/[@:].*$/, '').trim();
  }

  has(tool: string): boolean {
    return McpRegistry.normalize(tool) in this.manifest.tools;
  }

  get(tool: string): RegistryEntry | undefined {
    return this.manifest.tools[McpRegistry.normalize(tool)];
  }

  list(): string[] {
    return Object.keys(this.manifest.tools);
  }
}

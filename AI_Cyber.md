  
**TECHNICAL ARCHITECTURE SPECIFICATION**

**AI-Supervised CybersecurityTool Orchestration Platform**

5-Layer Architecture for MCP-Native, AI-Supervised, Automated Security Operations

| Document Type | Architecture Design Document (ADD) |
| :---- | :---- |
| **Version** | 2.0  |
| **Date** | June 26, 2026 |
| **Classification** | **CONFIDENTIAL — INTERNAL USE ONLY** |

# **1\. Executive Summary**

This document defines the complete technical architecture for an AI-Supervised Cybersecurity Tool Orchestration Platform. The platform addresses a fundamental gap in the current security tooling landscape: AI coding assistants (Claude Code, Gemini CLI, GitHub Copilot, GitLab Duo, Cursor, Codex) are powerful but unsupervised — they loop, waste tokens, pursue unproductive paths, and require constant human intervention. This platform replaces the human supervisor with an AI Supervisor Engine that watches everything, gives real-time corrective feedback, and keeps sub-agents on track.

The platform provides three foundational capabilities in one unified system:

* MCP-first tool dispatch: connects AI clients to security tools via MCP servers, with dynamic registry lookup and automatic routing.

* Terminal Automation (Sandbox Bypass): for tools without MCP servers, auto-installs them and automates them via PTY — identical in concept to how Google Assistant automates Android apps or OpenClaw automates WhatsApp — but for cybersecurity CLIs.

* AI Supervisor Engine: monitors all sub-agents in real time, detects loops and unproductive chains, manages token budgets, and injects corrective feedback before problems escalate. This is the paradigm shift: AI-supervised operations instead of human-supervised ones.

## **1.1 Architecture at a Glance**

| Architecture Style | 5-Layer Vertical Stack \+ Cross-cutting Supervisor |
| :---- | :---- |
| **Primary Language** | Python (core), supported by TypeScript, C, and Assembly, with Java used alongside them for higher-throughput, cross-platform performance-critical paths |
| **Protocol** | MCP (Model Context Protocol) — stdio, SSE, Streamable HTTP |
| **Supported AI Clients** | Claude API, Claude Code, Gemini CLI, GitHub Copilot, GitLab Duo, Cursor, Codex, Custom OpenAI-compat |
| **Tool Coverage Strategy** | MCP registry first → PTY terminal automation fallback (unlimited coverage) |
| **Supervisor Paradigm** | AI-to-AI supervision: Supervisor AI monitors Worker AI sub-agents |
| **Key Differentiators** | Loop detection, token budget management, feedback injection, auto-install cascade, multi-client |
| **Security Model** | RBAC \+ scope enforcement \+ confirmation gates \+ append-only audit log |
| **Install Method** | pip install \[name\] OR bun install \[name\] OR docker run \[image\] |
| **Target Platforms** | Kali Linux, Ubuntu, Debian, macOS, Windows (WSL2) |

# **2\. Design Philosophy & Core Principles**

This architecture is built on four design principles that directly address failure modes observed in existing systems. Every architectural decision traces back to one of these principles.

## **2.1 AI-Supervised, Not Human-Supervised**

The dominant paradigm in AI-assisted security tooling today is: AI executes tasks, a human watches the screen and intervenes when things go wrong. This is slow, expensive, does not scale, and creates the same bottleneck that AI was supposed to eliminate.

This platform inverts the model. The Supervisor Engine (Layer 5\) is an AI system that monitors all sub-agent activity, detects problems, and corrects them automatically — without human involvement in the loop. Humans only appear at three points: (1) giving the initial high-level command, (2) confirming high-risk destructive actions at confirmation gates, and (3) reviewing final output. Everything in between is AI-supervised.

This is the same model used by the most advanced autonomous systems in adjacent domains: Tesla's Autopilot supervisor monitors the driving model and overrides when confidence drops; AlphaFold's confidence scorer tells the structure predictor when to re-run; Waymo's meta-planner monitors the low-level planner and re-routes. The same pattern, applied to cybersecurity sub-agents.

## **2.2 MCP-First, Terminal-Fallback**

MCP (Model Context Protocol) provides structured, schema-validated, token-efficient communication between AI clients and tools. When an MCP server exists for a tool, it should always be used — the AI client receives typed inputs and outputs, not raw terminal noise.

However, the MCP ecosystem currently covers approximately 30–40 major security tools. There are hundreds of CLI-based security tools with no MCP server. The Terminal Automation Engine (Layer 4\) fills this gap by wrapping any CLI tool in a PTY subprocess, parsing its raw output into structured JSON, and presenting it to the AI client via a mock MCP interface. The client cannot tell the difference. This gives the platform unlimited tool coverage from day one, expanding automatically as the MCP ecosystem grows.

## **2.4 Token Efficiency as a First-Class Concern**

AI sub-agents running unmonitored consume tokens in predictable failure patterns: they loop over the same scan targets, re-read the same tool outputs, and research tangents that do not advance the task. The Supervisor Engine's token budget manager treats token consumption as a real-time constraint — not an afterthought. Each sub-agent gets a budget, consumption is tracked in real time, and the agent receives actionable redirection before the budget is exhausted. Internal benchmarks show 35–60% reduction in average session token cost versus unmanaged sub-agents running the same tasks.

# **3\. Architecture Overview**

The system is structured as five vertical layers (the AI Supervisor being the cross-cutting central one). Every user request passes through these layers. The Supervisor operates as a meta-layer that observes and influences layers 3, 4, and 5 in real time.

Note: a dedicated Security Layer (RBAC, scope enforcement, risk gating, and audit logging) is owned and implemented separately by the security team in accordance with their own policies and the laws of the relevant jurisdictions. It is intentionally not specified or built within this codebase, and the orchestration layers below make no assumptions about its internals.

## **3.1 Layer Stack**

| \# | Layer Name | Core Responsibility |
| ----- | :---- | :---- |
| **L1** | **AI Client Adapter** Multi-client bridge | Normalizes all incoming requests from every supported AI client (Claude API, Claude Code, Gemini CLI, GitHub Copilot, GitLab Duo, Cursor, Codex, custom OpenAI-compatible endpoints) into a unified internal TaskObject. Translates results back to each client's native format on return. |
| **L2** | **Task Router** Classifier & dispatcher | Receives a TaskObject from L1, classifies the tool requirement, checks the MCP registry, routes to L3 if an MCP server is available, or to L4 if not. Also manages parallelism and task queuing for multi-tool operations. |
| **L3** | **MCP Management Engine** Registry, lifecycle, routing | Maintains the live security tool MCP registry. Discovers servers via GitHub topic scan and mcp.so. Launches, health-checks, and gracefully shuts down MCP server processes. Handles all three MCP transports (stdio, SSE, Streamable HTTP). Enforces whitelist-only execution. |
| **L4** | **Terminal Automation Engine** PTY \+ auto-install | For tools with no MCP server: auto-installs via package manager cascade (apt/pip/cargo/go/npm/git), spawns tool in a PTY subprocess (handling interactive CLIs), parses raw output into structured JSON, and presents it via a mock MCP interface identical to real MCP. Enables unlimited tool coverage. |
| **L5** | **AI Supervisor Engine** Monitoring \+ feedback loop | The central brain. Monitors all sub-agents (Claude Code, Gemini CLI, etc.) in real time. Runs loop detection, progress scoring, and token budget management. Injects corrective feedback through sub-agent native channels. Manages human escalation gates. Optionally uses a separate Supervisor AI model for steering decisions. |

## **3.2 Data Flow Overview**

Below is the complete lifecycle of a single user request through the system:

| Step | Layer | What Happens |
| :---- | :---- | :---- |
| 1 | L1: Adapter | AI client sends request in its native protocol (JSON-RPC, REST, MCP, etc.). Adapter normalizes into a TaskObject with task\_id, source\_client, request\_type, target, constraints. |
| 2 | L5: Supervisor | Task Decomposer breaks complex request into sub-tasks. Assigns each to a sub-agent profile (different system prompts \+ tool whitelists per phase). Creates execution DAG. |
| 3 | L2: Router | For each sub-task: classifies tool requirement, queries MCP registry. Routes to L3 (MCP available) or L4 (no MCP). |
| 5a | L3: MCP | If MCP available: start MCP server process (if not already running), call tool via MCP protocol, receive structured response. |
| 5b | L4: Terminal | If no MCP: auto-install tool if missing, spawn PTY subprocess, execute, capture output, parse to structured JSON via regex/LLM parser. |
| 6 | L5: Supervisor | Supervisor monitors result: update loop detector, progress scorer, token counter. If anomaly detected: inject corrective feedback to sub-agent. If human gate triggered: pause and escalate. |
| 7 | L1: Adapter | Translate normalized result back to native AI client format. Return to sub-agent. |
| 8 | Repeat | Sub-agent processes result and calls next tool. Supervisor monitors the entire chain. Cycle continues until task complete or budget exhausted. |

# **4\. Layer 1 — AI Client Adapter**

The adapter layer is the system's universal input/output interface. It implements the same pattern as LSP (Language Server Protocol): each AI client has its own adapter module that speaks the client's native protocol, but internally all adapters produce and consume the same TaskObject and ResultObject schemas. Adding a new AI client requires only one new adapter module — zero changes to any other layer.

## **4.1 TaskObject Schema (Internal Standard)**

Every adapter normalizes its input into this schema:

{

  task\_id:        string (UUID v4),

  source\_client:  'claude\_api' | 'claude\_code' | 'gemini\_cli' | 'copilot' | 'gitlab\_duo' | 'cursor' | 'codex' | 'custom',

  request\_type:   'recon' | 'enumeration' | 'vuln\_scan' | 'exploit' | 'analysis' | 'report',

  natural\_input:  string (original user command),

  target:         { host: string, ports?: number\[\], paths?: string\[\] },

  tools\_hint:     string\[\] (optional tool preferences),

  context:        { session\_id, prior\_findings, active\_phase },

  constraints:    { scope\_id, max\_tokens, risk\_level, timeout\_ms }

}

## **4.2 Adapter Specifications**

| Client | Protocol | Registration Method | Key Implementation Detail |
| :---- | :---- | :---- | :---- |
| Claude API / SDK | REST HTTPS | Direct API key | System prompt injects tool manifest at session start. Adapter wraps tool responses as assistant messages in conversation history. |
| Claude Code | JSON-RPC over stdin/stdout | Registered as MCP server in .claude\_code/config.json | Platform launches Claude Code as subprocess. Claude Code connects back as MCP client. Adapter translates MCP tool\_call to TaskObject. |
| Gemini CLI / API | REST \+ subprocess | GEMINI\_API\_KEY env var | Tool manifest converted to Gemini function\_declarations schema. Adapter handles the different JSON structure for tool calls and responses. |
| GitHub Copilot | VS Code Extension API \+ localhost MCP | VS Code extension installs MCP endpoint | Platform exposes MCP server on localhost:PORT. VS Code extension connects Copilot to it. Same MCP flow as Claude Code from adapter's perspective. |
| GitLab Duo | MCP client via Duo Agent Platform | Duo agent config file | GitLab GA'd MCP support Q1 2026\. Adapter uses standard MCP server registration. Duo connects and issues tool\_call messages. |
| Cursor / Codex | MCP client | MCP server registration | Same MCP client pattern as Copilot. Platform exposes MCP endpoint; Cursor/Codex connects. No extra adapter code needed — MCP is the standard. |
| Custom AI | OpenAI-compatible REST | OPENAI\_API\_BASE env var | Any model serving the OpenAI /v1/chat/completions endpoint. Tool manifest converted to OpenAI-format function definitions. One line of config. |

# **5\. Layer 2 — Task Router & Dispatcher**

The Task Router is the system's central dispatcher. It receives a TaskObject from L1, classifies the type of security operation required, determines which tool or tools are needed, checks availability, and routes to L3 (MCP) or L4 (Terminal) accordingly. It also manages parallelism — multiple sub-tasks from the same decomposed request can execute concurrently, with results aggregated before returning to the sub-agent.

## **5.1 Tool Classification & Routing Logic**

| Phase | Tools (examples) | Typical Route | Parallelism |
| :---- | :---- | :---- | :---- |
| Recon / Discovery | Nmap, Subfinder, Shodan, Amass, theHarvester | MCP (if server exists) → Terminal fallback | High — run multiple discovery tools in parallel |
| Enumeration | Gobuster, ffuf, enum4linux, smbclient, ldapsearch | Terminal (most lack MCP servers) | Medium — parallelize where targets are independent |
| Vulnerability Scanning | Nuclei, Nessus (API), OpenVAS, Nikto | MCP preferred (Nuclei has official MCP) | High — scan multiple targets concurrently |
| Exploitation | Metasploit, sqlmap, Hydra | Terminal (interactive PTY required for msf) | Low — exploit sequentially with human gates |
| Reverse Engineering | Ghidra (MCP), Radare2, binwalk | MCP for Ghidra; Terminal for others | Medium — each binary independent |
| Post-Exploitation | YARA, Volatility, CyberChef | Terminal (most lack MCP) | Low — sequential analysis |
| Reporting | Internal formatter, Faraday API | Internal | N/A — aggregate and format |

## **5.2 Routing Decision Algorithm**

For each tool call dispatched by a sub-agent, the router executes this decision sequence:

1. Normalize tool name (lowercase, strip version suffixes).

2. Query MCP Registry (L3): Does a registered, trusted MCP server exist for this tool?

3. If YES: Is the MCP server already running and healthy? If yes, call directly. If no, start it (\< 2s lazy init).

4. If NO: Fall through to Terminal Automation Engine (L4). Check if the tool is installed. If not, run auto-installer cascade.

5. In both paths: hand the call off for execution (any policy/scope/audit enforcement is applied by the separately-owned security layer, outside this codebase).

6. Return normalized ToolResult to supervisor for monitoring, then to requesting sub-agent via L1 adapter.

# **6\. Layer 3 — MCP Management Engine**

The MCP Management Engine is the system's 'smart phone book and launch manager' for security tool MCP servers. It discovers available servers, manages their lifecycle, routes tool calls via the correct transport, and enforces whitelist-only execution. The design is directly inspired by FuzzingLabs/SecPipe's meta-MCP architecture — a single MCP endpoint that dynamically discovers and routes to subordinate MCP servers — but extended with broader registry coverage, cross-platform support, and automated launch.

## **6.1 Registry Architecture**

The tool registry is a versioned JSON manifest served from a hosted endpoint (with weekly auto-refresh and a local fallback cache):

{

  schema\_version: '2',

  last\_updated: '2026-06-26T00:00:00Z',

  tools: {

    'nmap': {

      mcp\_server: 'ghcr.io/org/nmap-mcp:latest',

      transport: 'stdio',

      install: { docker: '...', native: 'apt install nmap-mcp' },

      trust\_tier: 'official',  // official | community | experimental

      sha256: 'abc123...',

      tool\_schemas: \[ { name: 'scan', inputSchema: {...}, outputSchema: {...} } \]

    },

    'ghidra': {

      mcp\_server: 'github:bethington/ghidra-mcp@v2.1',

      transport: 'stdio',  // Ghidra MCP uses stdio transport

      trust\_tier: 'community',

      ...

    }

  }

}

## **6.2 Trust Tiers**

| Tier | Examples | Policy |
| :---- | :---- | :---- |
| Official | Nuclei MCP (Projectdiscovery), future CrowdStrike/Tenable servers | Auto-execute without prompt. Hash verified against registry. No confirmation needed. |
| Community | bethington/ghidra-mcp, FuzzingLabs/mcp-security-hub servers | First-run: display metadata \+ y/N prompt. Hash verified. After approval, auto-execute in same session. |
| Experimental | New additions to registry, \< 90 days old | Always prompt per-run until promoted to Community. Extra metadata displayed. |
| Unknown | Not in registry | Blocked. User sees: tool not in registry, cannot execute. Forces registry contribution workflow. |

## **6.3 Transport Support**

* stdio (Standard I/O): primary transport for CLI-native MCP servers. Claude Code and Gemini CLI use this. Server launched as child process; communication via stdin/stdout pipes.

* Server-Sent Events (SSE): for web-based AI clients. Server runs as HTTP endpoint; client subscribes to SSE stream for real-time tool call results.

* Streamable HTTP: for REST consumers and enterprise integrations. Stateless request/response over HTTPS. Supports connection pooling for high-throughput team scenarios.

All three transports are normalized internally — the task router and supervisor see the same ToolCall/ToolResult objects regardless of which transport was used.

# **7\. Layer 4 — Terminal Automation Engine**

The Terminal Automation Engine is the system's most novel component. It enables AI clients to use ANY command-line security tool — including interactive CLIs like msfconsole — as if it were a structured MCP server. The analogy is precise: this is what OpenClaw does for WhatsApp (driving a live app process via automated I/O), what Google Assistant does for Android apps, and what iOS Shortcuts/Siri Automation does for mobile apps. The difference is that this system targets command-line security tools rather than GUI apps.

## **7.1 PTY Wrapper (Pseudo-Terminal)**

Standard subprocess with pipes (subprocess.Popen in Python, child\_process.spawn in Node.js) cannot handle interactive CLIs. Tools like msfconsole, sqlmap \--wizard, and interactive Metasploit sessions require a real terminal environment — they use ncurses, readline, raw mode, and terminal control sequences. Without a PTY, these tools fail silently or output garbage.

* Implementation: node-pty (Node.js) or Python's ptyprocess — both allocate a real PTY and provide bidirectional read/write.

* Bidirectional I/O: the engine reads stdout/stderr in real time (streaming) and can write simulated keystrokes to simulate a human operator.

* Session persistence: PTY sessions for stateful tools (msfconsole, SQLMap sessions) are kept alive across multiple sub-agent calls. The sub-agent calls 'msf run module X' and then 'msf check session Y' — both go to the same persistent PTY session.

* Signal handling: the engine correctly forwards SIGINT (Ctrl-C), SIGTERM, and window resize signals to the PTY child — tools that poll terminal size work correctly.

* Timeout management: each PTY call has a configurable timeout. If a tool hangs waiting for input the engine cannot anticipate, the call fails gracefully with an informative error.

## **7.2 Auto-Installer Cascade**

When a tool is required but not installed, the engine runs this ordered cascade until one method succeeds or all fail:

| Step | Method | Condition | Example |
| :---- | :---- | :---- | :---- |
| 1 | apt-get install | Debian/Ubuntu/Kali detected (lsb\_release) | apt-get install \-y nmap nikto gobuster |
| 2 | pip install | Python package exists in registry | pip install nuclei-cli impacket |
| 3 | cargo install | Rust binary (Cargo.toml in repo) | cargo install feroxbuster rustscan |
| 4 | go install | Go module detected | go install github.com/OWASP/amass/v3/...@latest |
| 5 | npm install \-g | Node package found | npm install \-g js-beautify |
| 6 | brew install | macOS \+ Homebrew detected | brew install nikto hydra |
| 7 | winget install | Windows (WSL2 host) detected | winget install Wireshark.Wireshark |
| 8 | git clone \+ make | Fallback for tools with custom build | git clone \+ ./configure && make && sudo make install |
| 9 | Docker pull \+ run | Docker available, tool has official image | docker pull kalilinux/kali-rolling; docker run \--rm nmap... |
| FAIL | Graceful error | All methods failed | Returns structured error with manual install URL, OS-specific instructions |

## **7.3 Output Parser**

Raw terminal output from security tools is messy: ANSI escape codes, variable formatting, mixed text/data, and tool-specific conventions. The parser operates in two passes:

* Pass 1 — Known Format Library: regex/parser patterns for common tool output formats: Nmap XML (via nmap \-oX), Nmap grepable format (-oG), Nuclei JSONL, Nikto CSV, Gobuster text, Hydra output format, Metasploit session tables, SQLMap JSON, YARA rule match output, Masscan binary/XML. When format is recognized, a full typed ToolResult is produced.

* Pass 2 — LLM Fallback Parser: if no pattern matches, the raw output is sent to a small, fast language model (Claude claude-haiku-4-5 or equivalent) with the prompt: 'Parse this terminal output from \[tool\_name\] and return a JSON object with fields: findings\[\], status, errors\[\], metadata.' This covers new tools and uncommon output modes.

* Mock MCP Interface: the parsed ToolResult is wrapped in a standard MCP tool\_result envelope. The AI client calling the tool receives a schema-valid MCP response — it cannot tell whether the tool ran via real MCP or via PTY terminal automation.

# **8\. Layer 5 — AI Supervisor Engine (Core Differentiator)**

The AI Supervisor Engine is the platform's primary differentiator and the architectural innovation that no existing cybersecurity tool has implemented. It operates as a meta-layer that monitors every sub-agent (Claude Code, Gemini CLI, Cursor, etc.) executing security tasks in real time, detects failure modes before they become expensive, and injects corrective feedback through the sub-agent's own communication channel. The supervisor does not execute tools directly — it only observes and steers.

## **8.1 The Problem This Solves**

Unmonitored AI sub-agents running security tasks exhibit four recurring failure patterns that this engine prevents:

| Failure Pattern | What It Looks Like | Cost Without Supervisor |
| :---- | :---- | :---- |
| Scan Loops | Agent calls nmap on the same /24 subnet 4 times with identical parameters | 4x token cost, zero new findings, agent stuck |
| Research Spirals | Agent searches CVE database for 20 queries about a service version that is not vulnerable | 100K+ tokens wasted, task never advances |
| Phase Lock | Agent completes recon but never transitions to enumeration — keeps adding recon coverage | Infinite session duration, no output |
| Token Cliff | Agent uses 90% of token budget on early phases, cannot produce final report | Incomplete output, wasted budget, restart required |

## **8.2 Supervisor Sub-Components**

### **8.2.1 Task Decomposer & Execution Planner**

Receives the high-level user request and breaks it into a directed acyclic graph (DAG) of sub-tasks. Each node in the DAG is a phase-tagged sub-task with a tool whitelist, token budget allocation, time limit, and assigned sub-agent profile.

* Phase mapping: Recon → Enumeration → Vulnerability Analysis → Exploitation → Post-Exploitation → Reporting. Phases are sequential with dependency enforcement (exploitation cannot begin before enumeration is marked complete).

* Sub-agent profiles: different phases get different system prompts and different tool access. The recon sub-agent can use Shodan, Nmap, and Subfinder but not Metasploit. The exploit sub-agent can use Metasploit and Hydra but must have human gate confirmation before execution.

* Budget allocation: total session token budget is split across phases weighted by historical complexity (recon: 15%, enum: 20%, vuln scan: 25%, exploit: 25%, reporting: 15%). Each sub-agent receives its budget at task start.

* Re-planning: if a phase produces unexpected findings (e.g., recon reveals 400 open hosts instead of 3), the planner re-estimates sub-task complexity and reallocates budget before the next phase begins.

### **8.2.2 Sub-Agent Monitor**

The monitor maintains a per-sub-agent state object that is updated on every tool call:

SubAgentState {

  agent\_id:        string,

  current\_phase:   Phase,

  tool\_call\_log:   ToolCall\[\],        // sliding window, last 20 calls

  artifacts:       Artifact\[\],        // IPs, ports, CVEs, creds found

  tokens\_used:     number,

  tokens\_budget:   number,

  loop\_fire\_count: number,            // times loop detector has fired

  last\_new\_artifact\_at: timestamp,   // when last novel finding was made

  status:          'active'|'stalled'|'looping'|'budget\_warning'|'escalated'

}

### **8.2.3 Loop Detector**

The loop detector runs after every tool call and examines the sub-agent's recent call history for repetitive patterns:

* Algorithm: compute a fuzzy hash of each (tool\_name, target, key\_params) tuple. Compare each call against the last N calls using normalized edit distance. If similarity \> threshold across K consecutive calls, fire LOOP\_DETECTED.

* Per-category thresholds: Recon tools get a higher tolerance (more calls before loop fires) because scanning is inherently iterative. Exploit tools fire on fewer repetitions because repeated exploit attempts indicate either a loop or a dangerous pattern.

* Corrective feedback (not just 'stop'): the loop detector generates a specific redirect: 'You have called \[tool\] on \[target\] \[N\] times with near-identical parameters and found \[M\] new findings. The information you need is not there. Your next step should be \[alternative based on current findings\].' The sub-agent receives this as a tool\_result or injected system message and continues with the redirect.

* Loop fire escalation: if loop\_fire\_count reaches 3 on the same task, the supervisor escalates to human with a summary: 'Sub-agent has been redirected 3 times and continues looping. Recommend: manual investigation of \[specific area\] or task cancellation.'

### **8.2.4 Progress Scorer**

The progress scorer measures whether the sub-agent is generating new, actionable findings — or just making noise:

* Novel artifact tracking: after each tool call, the output is parsed for new artifacts (new IP addresses, new open ports, new CVE references, new file paths, new credentials, new domain names). These are deduplicated against the session artifact store.

* Productivity rate: new\_artifacts / tool\_calls\_since\_last\_novel\_finding. If this rate falls below a configurable threshold (default: 0 new artifacts in last 5 calls), fire LOW\_PRODUCTIVITY.

* Pivot injection: 'This chain has not generated new findings in the last \[N\] calls. Current known attack surface: \[summary\]. Recommended next step: \[specific suggestion based on phase and findings\].'

* Phase completion detection: if the progress scorer determines that a phase has reached diminishing returns (artifact rate near zero, coverage above threshold), it signals the Task Decomposer to advance to the next phase.

### **8.2.5 Token Budget Manager**

Real-time token consumption tracking with progressive interventions:

| Budget Level | Consumption | Supervisor Action |
| :---- | :---- | :---- |
| Monitor | \< 50% | No action. Track normally. |
| Watch | 50–70% | Log internally. Increase monitoring frequency. No injection. |
| Warn | 70–80% | Inject: 'You are at 70% of your task token budget. Prioritize the highest-impact remaining step. Skip low-confidence branches. Do not open new sub-investigations.' |
| Critical | 80–90% | Inject: 'You are at 85% of your task token budget. Complete the current step only. Begin preparing a partial findings summary.' |
| Force Wrap | \> 90% | Inject: 'Token budget at 90%. Stop all new tool calls. Summarize all findings discovered so far and mark the task as partial-complete. Include what was not investigated.' |
| Budget Exhausted | 100% | Force-terminate the sub-agent call chain. Return partial results. Log budget exhaustion in audit log. Supervisor escalates to human. |

Token counting: each AI client adapter implements its own token counter using the client's native tokenizer (cl100k\_base for Claude, tiktoken for OpenAI/Codex, SentencePiece for Gemini). A conservative 15% safety margin is applied to all budget calculations.

### **8.2.6 Feedback Injector**

The supervisor communicates with each sub-agent via the sub-agent's own native channel — it does not interrupt or replace the sub-agent, it speaks to it in its own language:

| Sub-Agent Type | Injection Channel | How It Works |
| :---- | :---- | :---- |
| API clients (Claude, Gemini, Custom) | System prompt injection mid-conversation | Supervisor inserts a new system message into the conversation history before the next tool call is processed by the AI client. |
| CLI clients (Claude Code, Gemini CLI) | stdin write to subprocess | Supervisor writes the feedback message to the CLI process's stdin, as if the user had typed it. The CLI processes it as a user input. |
| MCP-connected agents | tool\_result error field | Supervisor returns a tool\_result with isError=true and a structured corrective message in the content field. The MCP client sees a tool error with actionable guidance. |
| IDE agents (Copilot, GitLab Duo, Cursor) | VS Code extension messaging / MCP | Supervisor sends a message via the VS Code extension API or MCP error channel. Agent sees it as tool feedback. |

All feedback is ACTIONABLE — it tells the sub-agent specifically what to do next, not just that something is wrong. The feedback message always contains: (1) what was detected, (2) what it means, and (3) a specific recommended next action. This is critical: vague feedback ('you are looping') leads to confusion; specific feedback ('call nmap on the 192.168.2.x/24 range that was mentioned in the first scan but never enumerated') leads to progress.

### **8.2.7 Human Escalation Manager**

Five conditions trigger human escalation. The supervisor pauses the relevant sub-agent, generates a summary, and presents options to the human operator:

* HIGH\_RISK tool request: any tool classified as high-risk (exploit execution, credential dump, destructive actions, data exfiltration simulation) — see Layer 6\. Sub-agent sees: 'Waiting for human authorization. Tool: \[name\], Action: \[description\], Target: \[target\].'

* Scope boundary approach: sub-agent proposes action on a target that is at the edge of, or outside, the defined scope. Supervisor pauses with: 'Proposed target \[X\] is outside authorized scope. Confirm expand or deny.'

* Loop escalation: loop detector has fired 3 times on the same task. Supervisor has not been able to correct the loop automatically.

* Novel critical finding: a finding exceeds the confidence threshold for automatic handling (e.g., active exploit succeeded, credentials found, root access obtained). Supervisor presents: 'Critical finding — human review recommended before proceeding.'

* Sub-agent contradiction: sub-agent's proposed next action contradicts the phase plan in a way the supervisor cannot resolve automatically.




# **11\. Technology Stack**

| Component | Technology Choice | Rationale |
| :---- | :---- | :---- |
| Core Runtime | Python 3.12 (core) | Primary language for the core. Most security tool CLIs have Python bindings and many tools are Python packages themselves (impacket, scapy, etc.), making Python the natural orchestration core. |
| Supporting Languages | TypeScript 5.x, C, Assembly | TypeScript for MCP/AI-client adapters where the official MCP SDK is TypeScript-first and for IDE-side integrations; C and hand-tuned Assembly for the small set of latency-critical hot paths (parsing, fast hashing, PTY I/O loops) exposed to the Python core via native bindings. |
| Performance Layer | Java 26 | Used alongside the core for high-throughput, cross-platform performance-critical paths (concurrent sub-agent monitoring fan-out, parallel tool dispatch) where the JVM's mature concurrency and consistent cross-platform behavior give a measurable speed advantage. |
| PTY Library | ptyprocess (Python) / node-pty (TypeScript adapters) | Both provide real PTY allocation. ptyprocess used by the Python core for tool automation; node-pty available to TypeScript adapters where better Windows/WSL2 support is needed. |
| MCP SDK | @modelcontextprotocol/sdk (official) | Official TypeScript SDK. Handles all three transports (stdio, SSE, HTTP). Used for both client connections and server registration. |
| Internal Message Bus | Node.js EventEmitter \+ typed events | Zero-dependency, in-process pub/sub. Supervisor subscribes to ToolCall and ToolResult events. No external broker needed for single-host deployment. |
| Token Counting | tiktoken (NPM port) per AI client | cl100k\_base for Claude, p50k\_base for Codex/GPT-3.5, o200k\_base for GPT-4o, SentencePiece wrapper for Gemini. Each adapter implements its own counter. |
| Registry Cache | SQLite | Lightweight, zero-server, cross-platform. Stores registry manifest, server state, and session history. No external DB dependency for local install. |
| Configuration | YAML (js-yaml) \+ JSON Schema validation | Human-readable config.yaml for user settings, schema-validated to prevent misconfiguration. JSON for scope.json (industry convention). |
| Package Distribution | PyPI (pip) \+ bun \+ Docker Hub | Three distribution channels for maximum reach. pip for the Python-native core and security researchers, bun for fast install/runtime of the TypeScript adapters and developer tooling, Docker for enterprise/isolated environments. |
| Testing | Jest (unit) \+ Playwright (integration) | Jest for component testing of adapters, supervisor logic, routing. Playwright for end-to-end tests simulating real AI client interactions against mock tools. |


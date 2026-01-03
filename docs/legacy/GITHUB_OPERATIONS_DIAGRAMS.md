# GitHub Operations - Visual Diagrams

## 1. High-Level Architecture Diagram

```mermaid
graph TB
    subgraph GitHub["GitHub"]
        GHRepo["Repository"]
        GHAPI["GitHub API v3"]
        GHWebhook["Webhook Events"]
    end
    
    subgraph CodeRabbit["CodeRabbit System"]
        APIGateway["API Gateway"]
        WebhookHandler["Webhook Handler"]
        GitHubClient["GitHub Client"]
        ConfigLoader["Config Loader"]
        HybridAnalyzer["Hybrid Analyzer"]
        RAGOrch["RAG Orchestrator"]
        ProcessWorkers["Review Workers"]
    end
    
    subgraph External["External Services"]
        Redis["Redis Queue"]
        LLM["LLM/AI Model"]
        SAST["SAST Tools<br/>Semgrep"]
    end
    
    GHWebhook -->|1. PR Event| APIGateway
    APIGateway -->|2. Route| WebhookHandler
    WebhookHandler -->|3. Fetch PR Data| GitHubClient
    GitHubClient -->|GET /repos/.../pulls| GHAPI
    WebhookHandler -->|4. Load Config| ConfigLoader
    ConfigLoader -->|GET Contents| GHAPI
    WebhookHandler -->|5. Analyze| HybridAnalyzer
    HybridAnalyzer -->|Clone| GHRepo
    HybridAnalyzer -->|Run| SAST
    WebhookHandler -->|6. Enhance| RAGOrch
    WebhookHandler -->|7. Queue| Redis
    Redis -->|8. Process| ProcessWorkers
    ProcessWorkers -->|9. Analyze with| LLM
    ProcessWorkers -->|10. Post| GitHubClient
    GitHubClient -->|POST Review/Comment| GHAPI
    GHAPI -->|GitHub UI Update| GHRepo
```

---

## 2. Webhook Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Received: GitHub sends webhook
    
    Received --> Parsing: Parse JSON payload
    Parsing --> ActionCheck: Check action type
    
    ActionCheck --> Ignored: opened/synchronize/reopened?
    ActionCheck --> Ignored: ❌ Other action
    
    ActionCheck --> LoadConfig: ✅ Valid action
    
    LoadConfig --> ConfigLoaded: Load .coderabbit.yaml
    ConfigLoaded --> FetchFiles: Fetch PR files
    
    FetchFiles --> FilesRetrieved: Files received
    FilesRetrieved --> Analyze: Start analysis
    
    Analyze --> HybridAnalysis: Cloning enabled?
    Analyze --> APIOnly: ❌ No cloning
    
    HybridAnalysis --> RAGAnalysis: Clone & SAST complete
    APIOnly --> RAGAnalysis: API-only analysis done
    
    RAGAnalysis --> RAGEnrich: RAG enabled?
    RAGAnalysis --> Queued: ❌ No RAG
    
    RAGEnrich --> Queued: RAG enrichment done
    
    Queued --> JobQueued: Enqueue review job
    JobQueued --> Response: Return review_id
    Response --> [*]
    
    Ignored --> [*]: No action taken
```

---

## 3. Complete Request Flow with Components

```mermaid
sequenceDiagram
    participant User as Developer
    participant GitHub as GitHub<br/>Platform
    participant APIGateway as API<br/>Gateway
    participant WebhookH as Webhook<br/>Handler
    participant GitClient as Git<br/>Client
    participant ConfigL as Config<br/>Loader
    participant Analyzer as Hybrid<br/>Analyzer
    participant RAG as RAG<br/>Orchestrator
    participant Queue as Redis<br/>Queue
    participant Workers as Review<br/>Workers
    
    User->>+GitHub: Push commits to PR
    GitHub->>+APIGateway: POST /webhook/github
    APIGateway->>+WebhookH: Route webhook
    
    WebhookH->>WebhookH: Parse payload
    WebhookH->>WebhookH: Check action (opened/synchronize)
    
    WebhookH->>+ConfigL: Load config
    ConfigL->>+GitHub: GET .coderabbit.yaml
    GitHub-->>-ConfigL: Config file
    ConfigL-->>-WebhookH: Parsed config
    
    WebhookH->>+GitClient: Fetch PR files
    GitClient->>+GitHub: GET /pulls/{pr}/files
    GitHub-->>-GitClient: File list + diffs
    GitClient-->>-WebhookH: FileChange objects
    
    alt Cloning Enabled
        WebhookH->>+Analyzer: analyze_pr()
        Analyzer->>+GitHub: Clone repo
        GitHub-->>-Analyzer: Repository
        Analyzer->>Analyzer: Run SAST
        Analyzer-->>-WebhookH: Analysis results
    end
    
    alt RAG Enabled
        WebhookH->>+RAG: review_pr()
        RAG->>RAG: Find similar patterns
        RAG->>RAG: Link related issues
        RAG-->>-WebhookH: RAG context
    end
    
    WebhookH->>+Queue: enqueue_job()
    Queue->>Queue: Store review job
    Queue-->>-WebhookH: job_id
    
    WebhookH-->>-APIGateway: ReviewResponse {review_id}
    APIGateway-->>GitHub: HTTP 200
    GitHub-->>User: Webhook acknowledged
    
    Queue->>+Workers: Dequeue job
    Workers->>Workers: Run AI analysis
    Workers->>Workers: Generate comments
    Workers->>+GitClient: post_review()
    GitClient->>+GitHub: POST /reviews
    GitHub-->>-GitClient: Review posted
    GitClient-->>-Workers: Review ID
    Workers-->>-Queue: Complete
    
    GitHub->>User: 🔔 Review posted
    User->>GitHub: Read review comments
```

---

## 4. File Fetching Pipeline

```mermaid
graph LR
    Start["Start:<br/>PR Webhook"] -->|Extract PR #| GetFiles["GET /pulls/{pr}/files"]
    
    GetFiles -->|Returns Array| Parse["Parse File List<br/>{filename, status, patch}"]
    
    Parse -->|For Each File| CheckStatus{"Change<br/>Type?"}
    
    CheckStatus -->|added| AddType["✅ Added"]
    CheckStatus -->|removed| DelType["🗑️ Deleted"]
    CheckStatus -->|modified| ModType["✏️ Modified"]
    CheckStatus -->|renamed| RenType["↩️ Renamed"]
    
    AddType --> FetchContent["GET raw_url<br/>Fetch Content"]
    DelType --> FetchContent
    ModType --> FetchContent
    RenType --> FetchContent
    
    FetchContent --> Detect["Detect Language<br/>.ts → typescript"]
    
    Detect --> Create["Create FileChange<br/>Object"]
    
    Create --> Collect["Collect All Files"]
    
    Collect --> Complete["✅ Complete<br/>Vec<FileChange>"]
    
    Complete --> Use["Used by:<br/>- HybridAnalyzer<br/>- RAG Orchestrator<br/>- AI Analysis"]
```

---

## 5. Comment Webhook Interaction

```mermaid
sequenceDiagram
    participant User as Developer
    participant GitHub as GitHub
    participant APIGateway as API<br/>Gateway
    participant CommentH as Comment<br/>Handler
    participant GitClient as Git<br/>Client
    participant LLM as LLM<br/>Model
    
    User->>+GitHub: Post comment with<br/>@coderabbit
    GitHub->>+APIGateway: POST /webhook/github/comment
    APIGateway->>+CommentH: handle_comment_webhook()
    
    CommentH->>CommentH: Check action == "created"
    CommentH->>CommentH: Verify is PR comment
    CommentH->>CommentH: Check @coderabbit mentioned
    CommentH->>CommentH: Verify not from bot
    
    CommentH->>CommentH: Extract question<br/>Remove @mention
    
    CommentH->>+GitClient: fetch_pr_files()
    GitClient->>+GitHub: GET /pulls/{pr}/files
    GitHub-->>-GitClient: File list
    GitClient-->>-CommentH: FileChange objects
    
    CommentH->>+GitClient: load_comment_thread()
    GitClient->>+GitHub: GET /issues/{pr}/comments
    GitHub-->>-GitClient: Comments
    GitClient-->>-CommentH: Conversation history
    
    CommentH->>+LLM: generate_response()
    LLM->>LLM: Analyze question type
    LLM->>LLM: Build context
    LLM->>LLM: Generate answer
    LLM-->>-CommentH: Response text
    
    CommentH->>+GitClient: post_comment()
    GitClient->>+GitHub: POST /issues/{pr}/comments
    GitHub-->>-GitClient: Comment ID
    GitClient-->>-CommentH: Success
    
    CommentH-->>-APIGateway: CommentResponse
    APIGateway-->>GitHub: HTTP 200
    GitHub-->>User: ✅ Bot reply posted
```

---

## 6. Analysis Decision Tree

```mermaid
graph TD
    Start["📥 Webhook Received"]
    
    Start --> LoadConf["Load .coderabbit.yaml"]
    LoadConf --> ConfCheck{Config<br/>Found?}
    
    ConfCheck -->|❌ Missing| UseDefault["Use default config"]
    ConfCheck -->|✅ Found| ParseConf["Parse & validate"]
    UseDefault --> Clone1{Cloning<br/>Enabled?}
    ParseConf --> Clone1
    
    Clone1 -->|❌ No| APIOnly["📡 API-Only Analysis"]
    Clone1 -->|✅ Yes| Clone["🔄 Clone Repository"]
    Clone --> SAST{SAST<br/>Enabled?}
    
    SAST -->|✅ Yes| RunSAST["🔍 Run SAST Scanner<br/>Semgrep, etc."]
    SAST -->|❌ No| SkipSAST["⏭️ Skip SAST"]
    RunSAST --> SASTDone["📊 Get metrics"]
    SkipSAST --> SASTDone
    
    SASTDone --> RAG1{RAG<br/>Enabled?}
    APIOnly --> RAG1
    
    RAG1 -->|❌ No| NoRAG["⏭️ Skip RAG"]
    RAG1 -->|✅ Yes| RunRAG["🧠 RAG Analysis"]
    RunRAG --> RAGTimeout{Timeout<br/>5s?}
    
    RAGTimeout -->|⏱️ Yes| TimeoutRAG["⚠️ Skip, continue"]
    RAGTimeout -->|❌ No| RAGComplete["📚 Similar patterns,<br/>related issues,<br/>best practices"]
    TimeoutRAG --> NoRAG
    RAGComplete --> NoRAG
    
    NoRAG --> Queue["📤 Queue Review Job"]
    Queue --> Return["↩️ Return review_id"]
    Return --> [*]
```

---

## 7. Performance & Error Handling

```mermaid
graph TB
    subgraph Performance["⚡ Performance Optimizations"]
        A1["Async/Await<br/>Non-blocking IO"]
        A2["RAG Truncation<br/>Top 5 patterns<br/>Top 3 issues"]
        A3["Timeout Management<br/>5s RAG timeout"]
        A4["Lazy Initialization<br/>Singleton pattern"]
        A5["Job Queueing<br/>Async processing"]
    end
    
    subgraph Errors["🛡️ Error Handling"]
        E1["GitHub API Errors<br/>401/403/404/422/500"]
        E2["Config Errors<br/>Missing/Invalid YAML"]
        E3["Analysis Errors<br/>Clone fail → API only<br/>SAST timeout → continue<br/>RAG timeout → continue"]
        E4["Comment Errors<br/>Fetch fail → return 500<br/>Post fail → return error"]
        E5["Token Errors<br/>Invalid token → 401"]
    end
    
    subgraph Fallbacks["↩️ Graceful Fallbacks"]
        F1["No Config →<br/>Use defaults"]
        F2["Clone Failed →<br/>API-only analysis"]
        F3["SAST Timeout →<br/>Continue analysis"]
        F4["RAG Timeout →<br/>Continue without context"]
        F5["File Fetch Failed →<br/>Return empty content"]
    end
    
    Performance -->|Used in| Errors
    Errors -->|Triggers| Fallbacks
```

---

## 8. Security Architecture

```mermaid
graph TB
    subgraph Auth["🔐 Authentication"]
        T1["GitHub Token<br/>Environment: GITHUB_TOKEN<br/>Type: Fine-grained PAT<br/>or Classic Token"]
        T2["Bearer Token<br/>Header: Authorization<br/>Format: Bearer {token}"]
        T3["Webhook Secret<br/>Environment: GITHUB_WEBHOOK_SECRET<br/>HMAC-SHA256 validation"]
    end
    
    subgraph Validation["✓ Validation"]
        V1["Webhook Signature<br/>X-Hub-Signature header<br/>Compare HMAC"]
        V2["Event Source<br/>Verify from GitHub IP range<br/>Check event type"]
        V3["Bot Self-Check<br/>Comment author ≠ bot name<br/>Prevent loops"]
    end
    
    subgraph Storage["💾 Token Management"]
        S1["Environment Variables<br/>Never in code/logs"]
        S2["Rotation Policy<br/>Periodic refresh"]
        S3["Minimal Scope<br/>Only needed permissions"]
        S4["Access Logs<br/>Audit API calls"]
    end
    
    subgraph Transport["🔒 Transport Security"]
        TR1["HTTPS Only<br/>Enforced by reqwest"]
        TR2["No Token in URL<br/>Always in headers"]
        TR3["User-Agent Header<br/>Identify bot"]
    end
    
    Auth --> Validation
    Validation --> Storage
    Storage --> Transport
```

---

## 9. Multi-Platform Architecture

```mermaid
graph TB
    Webhook["Webhook Handler<br/>Platform Agnostic"]
    
    GitHub_WH["GitHub Webhook<br/>Payload Parser"]
    GitLab_WH["GitLab Webhook<br/>Payload Parser"]
    Azure_WH["Azure DevOps<br/>Webhook Parser"]
    
    GitHub_Client["GitHub API Client<br/>PR files, reviews,<br/>comments"]
    GitLab_Client["GitLab API Client<br/>MR files"]
    Azure_Client["Azure API Client<br/>PR files"]
    
    GitHub_Analysis["GitHub Analysis<br/>Hybrid + RAG +<br/>AI Review"]
    GitLab_Analysis["GitLab Analysis<br/>API-only +<br/>AI Review"]
    Azure_Analysis["Azure Analysis<br/>API-only +<br/>AI Review"]
    
    GitHub_Post["GitHub Post<br/>Reviews & Comments"]
    GitLab_Post["GitLab Post<br/>Comments only"]
    Azure_Post["Azure Post<br/>Comments only"]
    
    Webhook -->|/webhook/github| GitHub_WH
    Webhook -->|/webhook/gitlab| GitLab_WH
    Webhook -->|/webhook/azure| Azure_WH
    
    GitHub_WH -->|Use| GitHub_Client
    GitLab_WH -->|Use| GitLab_Client
    Azure_WH -->|Use| Azure_Client
    
    GitHub_Client --> GitHub_Analysis
    GitLab_Client --> GitLab_Analysis
    Azure_Client --> Azure_Analysis
    
    GitHub_Analysis --> GitHub_Post
    GitLab_Analysis --> GitLab_Post
    Azure_Analysis --> Azure_Post
```

---

## 10. Data Flow - From PR Event to Posted Review

```mermaid
graph LR
    subgraph Input["1️⃣ Input"]
        I1["GitHub Webhook<br/>PR opened/updated"]
    end
    
    subgraph Fetch["2️⃣ Fetch Data"]
        F1["PR metadata"]
        F2["PR files & diffs"]
        F3["Configuration file"]
        F4[".coderabbit.yaml"]
    end
    
    subgraph Analyze["3️⃣ Analyze"]
        A1["Hybrid Analysis<br/>Code metrics<br/>SAST results"]
        A2["RAG Analysis<br/>Similar patterns<br/>Related issues<br/>Best practices"]
        A3["AI/LLM Analysis<br/>Generate insights<br/>Write comments"]
    end
    
    subgraph Process["4️⃣ Process"]
        P1["Format review<br/>body & comments"]
        P2["Calculate metrics"]
        P3["Prepare payload"]
    end
    
    subgraph Output["5️⃣ Output"]
        O1["POST /reviews"]
        O2["GitHub receives<br/>review"]
        O3["PR updated with<br/>comments"]
        O4["Developer<br/>notified"]
    end
    
    Input --> Fetch
    Fetch -->|GitHub API| Analyze
    Analyze --> Process
    Process --> Output
```

---

## 11. Configuration Flow

```mermaid
flowchart LR
    Start["🔍 Config Load Start"]
    
    Start -->|Owner, Repo, Branch| Fetch["GET /repos/{owner}/{repo}<br/>/contents/.coderabbit.yaml<br/>?ref={branch}"]
    
    Fetch -->|HTTP 200| Parse["Parse YAML<br/>Schema validation"]
    Fetch -->|HTTP 404| NotFound["Config not found"]
    Fetch -->|HTTP Error| Failed["Fetch failed"]
    
    Parse -->|Valid| Settings["Extract Settings<br/>sast.enabled<br/>cloning.enabled<br/>rag.enabled<br/>review_rules<br/>ai_settings"]
    Parse -->|Invalid| Failed
    
    NotFound -->|Use| Default["Default Config<br/>All features OFF<br/>Standard rules"]
    Failed -->|Use| Default
    
    Settings --> Store["Cache in memory<br/>for this request"]
    Default --> Store
    
    Store --> Ready["✅ Config Ready<br/>Used for analysis<br/>decisions"]
```

---

## 12. Review Posting Detail

```mermaid
sequenceDiagram
    participant Workers as Workers
    participant GitClient as GitHubClient
    participant GitHub as GitHub API
    participant UI as GitHub UI
    
    Workers->>Workers: 🧠 AI Analysis complete
    Workers->>Workers: Generate review body
    Workers->>Workers: Create inline comments
    
    Workers->>+GitClient: post_review(
    GitClient->>GitClient: Build request body
    GitClient->>GitClient: JSON payload:
    GitClient->>GitClient: - body: review text
    GitClient->>GitClient: - event: COMMENT/REQUEST_CHANGES
    GitClient->>GitClient: - comments: [
    GitClient->>GitClient: &nbsp;&nbsp;{path, position, body}
    GitClient->>GitClient: ]
    
    GitClient->>+GitHub: POST /repos/{o}/{r}/pulls/{pr}/reviews
    Note over GitHub: Validate request<br/>Check permissions<br/>Create review object
    GitHub-->>-GitClient: 201 Created<br/>Review ID
    
    GitClient-->>-Workers: Review ID
    
    GitHub->>+UI: Update PR view
    UI->>UI: Render review<br/>Show comments
    UI->>UI: Notify author
    UI-->>-GitHub: ACK
    
    Note over GitHub,UI: Developer sees review<br/>in PR timeline
```

---

## 13. RAG Context Integration

```mermaid
graph TB
    Files["PR Files"]
    
    Files -->|Feed to RAG| RAG["🧠 RAG Orchestrator"]
    
    RAG -->|Query| Vec1["Vector Database<br/>Code embeddings"]
    RAG -->|Query| Vec2["Issue Database<br/>Issue embeddings"]
    RAG -->|Query| Vec3["Practice Database<br/>Best practice embeddings"]
    
    Vec1 -->|Top 5| Patterns["Similar Code<br/>Patterns"]
    Vec2 -->|Top 3| Issues["Related<br/>Issues"]
    Vec3 -->|Top 3| Practices["Best<br/>Practices"]
    
    Patterns -->|Truncate<br/>500 chars| Truncate1["Snippet"]
    Issues -->|Truncate<br/>300 chars| Truncate2["Description"]
    Practices -->|Keep| Truncate3["Full text"]
    
    Truncate1 --> Context["RagContextData<br/>Object"]
    Truncate2 --> Context
    Truncate3 --> Context
    
    Context -->|Include in| ReviewRequest["ReviewRequest<br/>Payload"]
    
    ReviewRequest -->|Sent to| Workers["Review Workers"]
    Workers -->|Use in| Prompt["LLM Prompt<br/>with context"]
    Prompt -->|Inform| Analysis["Better analysis<br/>with context"]
```

---

## 14. Error Recovery Paths

```mermaid
graph TD
    Start["Request Processing"]
    
    Start --> APICall["GitHub API Call"]
    
    APICall -->|Success| OK["✅ Continue"]
    APICall -->|401| Token401["❌ Invalid Token"]
    APICall -->|403| Perm403["❌ No Permission"]
    APICall -->|404| NotFound404["❌ Resource Missing"]
    APICall -->|422| BadReq["❌ Invalid Request"]
    APICall -->|5xx| Server500["❌ GitHub Down"]
    
    Token401 -->|Action| LogToken["Log error<br/>Alert admin"]
    Perm403 -->|Action| LogPerm["Log error<br/>Alert admin"]
    NotFound404 -->|Action| Fallback404["Fallback to<br/>defaults"]
    BadReq -->|Action| Fallback422["Retry with<br/>adjusted params"]
    Server500 -->|Action| Retry500["Exponential<br/>backoff retry"]
    
    LogToken --> Stop1["Stop processing"]
    LogPerm --> Stop2["Stop processing"]
    Fallback404 --> Continue["Continue with<br/>degraded mode"]
    Fallback422 --> Continue
    Retry500 --> APICall
    
    OK --> Continue
    Continue --> Complete["✅ Processing<br/>Complete"]
```

---

## 15. Request/Response Examples

### GitHub PR Webhook Payload Structure
```mermaid
graph TD
    Webhook["GitHub Webhook<br/>POST /webhook/github"]
    
    Webhook --> Action["action: 'opened'<br/>'synchronize'<br/>'reopened'"]
    Webhook --> PR["pull_request<br/>{...}"]
    Webhook --> Repo["repository<br/>{...}"]
    
    PR --> PRD1["id, number, title"]
    PR --> PRD2["body, state"]
    PR --> PRD3["html_url, diff_url"]
    PR --> PRD4["head: {ref, sha}"]
    PR --> PRD5["base: {ref, sha}"]
    PR --> PRD6["user: {id, login}"]
    PR --> PRD7["labels: [{name}]"]
    
    Repo --> RD1["id, name, full_name"]
    Repo --> RD2["clone_url"]
    Repo --> RD3["owner: {login}"]
    Repo --> RD4["default_branch"]
```


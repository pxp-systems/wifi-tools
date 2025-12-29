---
config:
  layout: elk
---

flowchart TB

    %% ===========================
    %% External Entities
    %% ===========================
    W["Holder Wallet"]
    B["Business Connect (Issuance Orchestrator)"]
    N["NZBN API"]
    R["Register / Status Change Batch Jobs"]
    G["GBG API"]

    %% ===========================
    %% Internal Processes
    %% ===========================
    Man_Issue["Manage Issuance (BC)"]
    Man_Id["Manage Identity Session (BC)"]
    Gen_Cred["Generate Credential (mDoc / VC)"]
    Pub_Status["Update Credential Status / Revocation (Mattr)"]
    Mattr_Issue["Mattr Issuance"]
    GBG_Session["GBG Identity Session"]
    GBG_UI["GBG Web UI (Manual Review)"]
    OTP_Svc["OTP Services"]

    %% ===========================
    %% Data Stores (IA References)
    %% ===========================
    IA01b[("IA-01b — Session State Cache")]
    IA02[("IA-02 — Verifiable Credential")]
    IA03[("IA-03 — GBG Database")]
    IA05[("IA-05 — Status List Registry")]
    IA07[("IA-07 — Business Connect Database")]
    IA08[("IA-08 — Azure Log Analytics Workspace")]
    IA09[("IA-09 — Credential Template Config")]
    IA10[("IA-10 — Issuer Signing Keys")]
    IA12[("IA-12 — NZBN Credential Metadata")]

    %% ===========================
    %% Business Connect Flow
    %% ===========================
    B -->|"(1) Start issuance (NZBN reference, metadata)"| Man_Issue
    B -->|"(2) Create identity session"| Man_Id
    B -->|"(3) Proof email and phone number"| OTP_Svc
    B -->|"(4) Retrieve validated attributes"| G

    OTP_Svc -->|"(5) Write OTP log"| IA07
    Man_Issue -->|"(6) /createUse and /createOffer requests"| Mattr_Issue
    Man_Issue -->|"(7) Store session tokens / context"| IA01b
    Man_Id -->|"(8) Identity check request"| GBG_Session
    Man_Id -->|"(9) Store session tokens / context"| IA01b

    %% ===========================
    %% Mattr VII Flow
    %% ===========================
    Mattr_Issue -->|"(10) Invoke credential generation"| Gen_Cred
    Gen_Cred -->|"(11) Issue mDoc / VC"| W
    Gen_Cred -->|"(12) Completed issuances (webhook)"| N
    Gen_Cred -->|"(13) Update revocation index"| Pub_Status

    IA09 -->|"(14) Read credential definition"| Gen_Cred
    IA10 -->|"(15) Sign credential using keys"| Gen_Cred
    Pub_Status -->|"(16) Update revocation list"| IA05

    %% ===========================
    %% GBG Integration
    %% ===========================
    GBG_Session -->|"(17) Write session and error logs"| IA03
    IA03 -->|"(18) Push validated / failed passport data + selfie sample"| G
    GBG_UI -->|"(19) Manual case review outcome"| IA03

    %% ===========================
    %% Logging & Monitoring
    %% ===========================
    Gen_Cred -->|"(20) Emit telemetry / events"| IA08
    Man_Issue -->|"(21) Behavioural logs"| IA07

    %% ===========================
    %% Data Relationships
    %% ===========================
    N -->|"(22) CredentialId, NZBN, UserId, status"| Pub_Status
    W -->|"(23) Store issued credential"| IA02
    R -->|"(24) Register entity state change events"| N
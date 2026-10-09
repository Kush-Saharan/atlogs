# Maintenance of Unstructured Logs — Project Context

## 1. Overview

**Maintenance of Unstructured Logs** is an AI-assisted maintenance decision-support system. Its purpose is to turn free-text maintenance logs into structured, searchable records and use those records to help maintenance personnel investigate recurring issues, assess risk, prioritise work, and plan maintenance.

The system is intended to **support human decisions**, not to operate machinery or make maintenance decisions without approval.

### Core flow

```text
Unstructured maintenance logs
            |
            v
    Validate and store logs
            |
            v
   Extract information with NLP
            |
            v
  Review and structure the records
            |
            v
  Link equipment, symptoms, and actions
            |
            v
  Retrieve similar historical cases
            |
            v
     Assess potential failure risk
            |
            v
  Recommend a maintenance priority
            |
            v
  Propose a resource-aware schedule
            |
            v
     Dashboard and notifications
            |
            v
      Human review and decision
            |
            v
       Audit/decision history
```

This is the intended logical flow. The exact implementation may differ.

## 2. Problem the System Addresses

Maintenance information is often written as free text. Different people may describe the same symptom using different words, abbreviations, or sentence structures.

For example:

- “Motor overheated during operation.”
- “Excessive temperature observed in the motor assembly.”
- “Motor temperature was above the normal range.”

These descriptions may refer to similar issues, but simple keyword matching may not identify them reliably.

This creates several challenges:

1. **Unstructured information:** Important fields are buried in paragraphs.
2. **Difficult historical search:** People may have to read many old records to find useful cases.
3. **Recurring issues are harder to identify:** Similar failures may be recorded using different terminology.
4. **Inconsistent prioritisation:** It can be difficult to compare urgency across maintenance requests.
5. **Resource constraints:** An urgent task may require a technician, spare part, or time slot that is unavailable.
6. **Limited traceability:** Users need to understand why a recommendation was made and what evidence informed the final decision.

The system aims to make maintenance records easier to search and reuse, while providing evidence-based assistance for planning.

## 3. Main Objectives

- Accept and preserve unstructured maintenance logs.
- Extract useful fields from log text.
- Allow users to review and correct extracted information.
- Standardise terminology where possible.
- Represent relationships between equipment, components, symptoms, failures, and actions.
- Retrieve similar historical maintenance cases.
- Estimate or indicate potential failure risk from available information.
- Recommend a maintenance priority and explain why.
- Propose a schedule that considers available resources.
- Display records, evidence, and recommendations in a dashboard.
- Notify relevant users about important issues.
- Maintain an audit trail of recommendations and final decisions.

## 4. Main Users

### Maintenance Engineer

- Uploads maintenance logs.
- Reviews and corrects extracted fields.
- Searches for similar historical cases.
- Examines risk indicators and priority recommendations.

### Maintenance Manager

- Reviews recommendations and their supporting evidence.
- Approves, modifies, or rejects recommendations.
- Reviews resource availability and proposed schedules.
- Monitors maintenance status and decision history.

### System Administrator

- Manages user accounts and access permissions.
- Maintains application configuration.
- Supports the application's operation.

## 5. Main Modules

### Module 1 — Log Input and Storage

**Purpose:** Receive, validate, identify, and preserve maintenance logs.

Intended workflow:

1. An authorised user selects a log file or submits log text.
2. The application validates the input format and required information.
3. It checks for duplicates where practical.
4. It assigns a unique identifier to the log.
5. It preserves the original text.
6. It records a processing status.
7. It sends the log for information extraction.

Possible error handling:

- Unsupported file type: show a validation error.
- Duplicate log: warn the user and allow them to decide how to proceed.
- Interrupted upload: mark the upload as failed and ask the user to retry.
- Unreadable content: preserve what was received and report that processing failed.

**Output:** A raw log with an ID, metadata, original text, and processing status.

### Module 2 — NLP Information Extraction

**Purpose:** Convert free-text maintenance notes into structured fields.

Possible fields include:

- Equipment identifier or name.
- Component.
- Symptom.
- Failure-related terms.
- Maintenance action.
- Date or time.
- Maintenance event and outcome, when stated.

Example input:

> On 12 August, pump P-104 experienced excessive vibration near its motor bearing. The technician replaced the bearing and tested the equipment successfully.

Illustrative extraction:

| Field | Extracted value |
|---|---|
| Date | 12 August |
| Equipment | Pump P-104 |
| Component | Motor bearing |
| Symptom | Excessive vibration |
| Action | Bearing replacement |
| Outcome | Equipment tested successfully |

Intended processing steps:

1. Read the stored text.
2. Clean and normalise text without replacing the original.
3. Split text into sentences or other useful units.
4. Identify equipment, components, symptoms, actions, dates, and failure-related terms.
5. Associate the extracted entities with the relevant maintenance event.
6. Normalise terminology where a known equivalent exists.
7. Assign confidence values if the chosen extraction approach supports them.
8. Show extracted fields and their source text to the user.
9. Flag uncertain fields for review.
10. Allow the user to correct extracted values.
11. Save the reviewed structured record.

The extraction must consider context. For example, “the bearing was not replaced” should not be interpreted as confirmation that a replacement occurred just because the word “replaced” appears.

Possible approaches include rule-based patterns, known equipment identifiers, spaCy, named-entity recognition, and transformer-based models. The final approach should be chosen during implementation and evaluation.

**Output:** Structured maintenance data linked to its original log.

### Module 3 — Knowledge Representation

**Purpose:** Record relationships among equipment, components, symptoms, failures, actions, and maintenance cases.

Illustrative relationship:

```text
Equipment: Pump P-104
    |
    | contains
    v
Component: Motor bearing
    |
    | experienced
    v
Symptom: Excessive vibration
    |
    | addressed by
    v
Action: Bearing replacement
    |
    | recorded in
    v
Maintenance case: CASE-1042
```

Intended workflow:

1. Read a reviewed structured record.
2. Map the extracted fields to entities.
3. Create or update relationships between entities.
4. Link the maintenance event to the affected equipment and component.
5. Reuse existing entities when appropriate.
6. Save the updated representation.
7. Handle update failures without silently losing existing information.

A graph database such as Neo4j is one possible implementation. A relational database can also store these relationships; the choice depends on the application's query and data needs.

**Output:** Connected maintenance knowledge that can be searched and explored.

### Module 4 — Historical Case Retrieval

**Purpose:** Find previous cases that resemble a current maintenance issue.

Example current issue:

> The motor is overheating and showing abnormal vibration.

Potential results might include earlier motor-overheating cases, motor-bearing vibration cases, or cooling-related cases. Unrelated cases should rank lower.

Intended workflow:

1. The user selects a current record or enters an issue description.
2. The system creates a searchable representation of the issue.
3. It searches the historical case store.
4. It ranks potential matches by similarity.
5. It displays matching cases with relevant equipment, symptoms, actions, and outcomes.
6. It allows filters such as equipment, component, or time period where supported.
7. If no sufficiently relevant match is found, it reports that clearly.

FAISS is a possible tool for vector similarity search. A possible implementation would create embeddings for historical cases, index them, embed the current issue, and retrieve nearby vectors. The retrieved records must remain linked to their source logs.

**Output:** Ranked historical cases that can inform the current investigation.

### Module 5 — Failure-Risk Assessment

**Purpose:** Provide an indicator of how concerning a maintenance issue may be, based on available records.

Potential inputs include:

- Frequency of similar failures.
- Recent symptoms or incidents.
- Repeated problems involving the same component.
- Equipment history.
- Equipment criticality, if this information is available.
- Similar historical cases and their outcomes.

Intended workflow:

1. Gather the current structured record and relevant history.
2. Calculate features or indicators from the available data.
3. Apply the selected scoring method or trained model.
4. Produce a risk score or category.
5. Show the factors that contributed to the result.
6. Indicate uncertainty or insufficient evidence when appropriate.
7. Store the assessment with its timestamp and input references.

The exact model is not established by the design description. A simple, explainable baseline may be appropriate before introducing a more complex machine-learning model. Any score must be evaluated against suitable historical outcomes before being treated as reliable.

**Output:** A risk indicator with supporting factors and a record of the assessment.

### Module 6 — Priority Recommendation and Scheduling

**Purpose:** Recommend which maintenance work should be addressed first and help propose a feasible schedule.

Potential priority factors:

- Assessed risk.
- Urgency stated in the log.
- Equipment criticality.
- Similar historical cases.
- Recurrence of the problem.
- Availability of required resources.

Intended workflow:

1. Gather the issue details, risk assessment, and relevant historical evidence.
2. Calculate or assign a priority.
3. Explain the main reasons for that priority.
4. Check constraints such as technician availability, spare parts, expected duration, and time slots.
5. Propose a schedule that respects the available constraints.
6. Flag a task that cannot be scheduled with the currently available resources.
7. Allow the responsible human to review and confirm or change the proposal.

Google OR-Tools is one possible option for constraint-based scheduling. It is not necessary to adopt it before the requirements and constraints are understood.

The priority score and schedule are separate concerns: an issue may be very urgent but still require escalation if the necessary resource is unavailable.

**Output:** An explainable priority recommendation and a proposed schedule.

### Module 7 — Dashboard and Notifications

**Purpose:** Give users a single place to inspect maintenance records and act on recommendations.

The dashboard may display:

- Uploaded logs and processing status.
- Extracted fields.
- Fields awaiting review.
- Historical cases similar to the current issue.
- Risk indicators and contributing factors.
- Recommended priority and explanation.
- Resource availability and proposed schedules.
- Alerts for high-priority issues.
- Decisions and current maintenance status.

Intended workflow:

1. The user opens the dashboard.
2. The system retrieves information permitted for that user.
3. The interface presents records and their status.
4. The user opens a record to inspect details and supporting evidence.
5. The application shows relevant notifications.
6. User actions update the record and status.

Notifications should be tied to a clear event or condition, such as a high-priority recommendation or a pending review. Delivery channels and notification rules need to be defined during implementation.

**Output:** A usable overview of maintenance work, evidence, and required actions.

### Module 8 — Decision Logging and Audit Trail

**Purpose:** Preserve what the system recommended and what the responsible person decided.

An audit record may include:

- Original recommendation.
- Final decision: approved, modified, or rejected.
- User who made the decision.
- Timestamp.
- Reason or comment, where supplied.
- Related maintenance record and source log.
- Evidence used for the recommendation.
- Schedule or assignment changes.

Intended workflow:

1. The system creates a recommendation.
2. The responsible user reviews it.
3. The user approves, modifies, or rejects it.
4. The application stores the recommendation and final decision.
5. The application records who acted and when.
6. Later users can inspect the decision history, subject to access permissions.

The audit trail should not silently overwrite the original recommendation when a user changes it. It should preserve enough history to distinguish the original proposal from the final decision.

**Output:** Traceable maintenance decisions and changes.

## 6. Example: One Issue Through the Whole System

The following example is illustrative; it is not a claim that this exact record exists in the current dataset.

### Step 1 — Input

A technician submits:

> Pump P-104 experienced excessive vibration around the motor bearing. The bearing was replaced and the pump was tested.

### Step 2 — Extraction

The NLP module identifies:

- Equipment: Pump P-104
- Component: Motor bearing
- Symptom: Excessive vibration
- Action: Bearing replacement
- Outcome: Pump tested

A user reviews the fields and corrects any mistakes.

### Step 3 — Relationship creation

The system links Pump P-104 to the motor bearing, the vibration symptom, the replacement action, and the maintenance event.

### Step 4 — Historical search

The system retrieves previous cases involving similar symptoms, components, or equipment.

### Step 5 — Risk assessment

The risk module uses the available history and current issue details to produce an indicator. If the historical evidence is insufficient, it should state that limitation rather than imply certainty.

### Step 6 — Priority recommendation

The system recommends a priority and displays the factors behind it.

### Step 7 — Schedule proposal

The system checks resource constraints and proposes a schedule. If a necessary technician or part is unavailable, it flags the conflict.

### Step 8 — Human decision

The responsible person reviews the evidence and approves, modifies, or rejects the proposal.

### Step 9 — Audit

The application records the recommendation, final decision, person, timestamp, and relevant evidence.

## 7. Suggested Technology Options

These are **candidate technologies**, not a declaration that every item is already being used.

| Area | Possible technology | Purpose |
|---|---|---|
| Backend language | Python | Application logic and data processing |
| NLP | spaCy or transformer models | Extract entities and information from logs |
| Traditional ML | scikit-learn | Baseline scoring or predictive models |
| Graph representation | Neo4j, or relational tables | Store relationships among entities |
| Similarity search | FAISS | Retrieve similar cases from vector embeddings |
| Main database | PostgreSQL | Store users, logs, structured records, resources, and decisions |
| Scheduling | Google OR-Tools | Explore feasible schedules under constraints |
| Backend API | FastAPI | Expose application operations through APIs |
| Frontend | React | Build the user interface and dashboard |

### A practical selection principle

Do not introduce every technology immediately. Begin with a small, working pipeline:

1. Store a log and its original text.
2. Extract a few fields.
3. Let a user correct them.
4. Store the reviewed record.
5. Search previous records.
6. Add risk scoring and scheduling only after suitable data and evaluation criteria exist.

The application can begin with a relational database. A graph database or vector index should be added when the relevant relationships or similarity-search requirements justify them.

## 8. Suggested Data Organisation

The application needs to keep raw evidence separate from processed information and decisions.

### Logical data stores

| Store | What it contains |
|---|---|
| Raw logs | Original log text or file reference, upload metadata, processing status |
| Structured records | Extracted and reviewed equipment, component, symptom, action, date, and outcome fields |
| Historical cases | Searchable maintenance cases, their symptoms, actions, and outcomes |
| Equipment data | Equipment identifiers, descriptions, components, and criticality where available |
| Resource data | Technicians, skills, availability, spare parts, and other scheduling constraints |
| Risk assessments | Score/category, contributing factors, model or method version, timestamp |
| Recommendations and schedules | Priority recommendation, explanation, proposed assignments, and schedule |
| Decision/audit records | Approvals, modifications, rejections, users, timestamps, and comments |
| Terminology reference | Canonical terms, abbreviations, and recognised synonyms |

These are logical categories. They do not have to be implemented as separate physical databases.

### Possible relational tables

A PostgreSQL design could use tables such as:

- `Users`
- `Equipment`
- `MaintenanceLogs`
- `MaintenanceRecords`
- `HistoricalCases`
- `Terminology`
- `RiskAssessments`
- `Recommendations`
- `Resources`
- `MaintenanceSchedules`
- `DecisionAudit`

Possible relationships:

```text
Users
  └── reviews/decides on ──> Recommendations

MaintenanceLogs
  └── produces ────────────> MaintenanceRecords
                                 |
                                 ├── refers to ──> Equipment
                                 ├── describes ──> Components/Symptoms
                                 └── links to ───> HistoricalCases

MaintenanceRecords
  └── assessed by ─────────> RiskAssessments
                                  |
                                  v
                            Recommendations
                                  |
                                  v
                         MaintenanceSchedules
                                  |
                                  v
                            DecisionAudit
```

Use foreign keys or equivalent references to connect related records. Preserve the source log identifier on each structured record so users can verify extracted information against the original text.

## 9. API and Application Boundaries

If the system uses a separate frontend and backend, the backend should own validation, permissions, processing, and database updates. The frontend should present information and send user actions through an API.

Possible API groups include:

- **Authentication and users:** sign in, user profile, role and access management.
- **Logs:** upload, list, view, validate, and check processing status.
- **Extraction/review:** retrieve extracted fields and submit corrections.
- **Historical search:** search and view similar cases.
- **Risk:** request and view a risk assessment.
- **Recommendations:** create, list, and inspect recommendations and explanations.
- **Scheduling:** view resources, propose a schedule, and confirm changes.
- **Decisions/audit:** approve, modify, reject, and inspect decision history.
- **Dashboard/notifications:** retrieve summaries, alerts, and pending actions.

These are API design suggestions. Exact endpoint paths, payloads, authentication mechanism, and response formats must be specified during implementation.

## 10. Functional Requirements in Plain Language

The system should support the following functional behaviours:

1. Accept maintenance logs and validate the input.
2. Preserve the original log content.
3. Extract structured fields from the log.
4. Allow users to review and correct extracted fields.
5. Normalise known terminology and abbreviations.
6. Represent relationships among equipment, symptoms, components, and actions.
7. Retrieve relevant historical cases.
8. Generate a risk indicator from available evidence.
9. Recommend a maintenance priority.
10. Explain recommendations with relevant factors and historical evidence.
11. Allow an authorised user to approve, modify, or reject a recommendation.
12. Propose schedules while considering available resources.
13. Notify users about relevant high-priority issues or pending work.
14. Keep a traceable record of recommendations and final decisions.

## 11. Non-Functional Requirements

These describe how well the application should work, rather than only what actions it supports.

- **Usability:** users should be able to review records and understand recommendations without unnecessary complexity.
- **Security:** users should only access operations and records permitted by their roles.
- **Traceability:** processed records and decisions should link back to their sources.
- **Robustness:** malformed input and failed processing should be handled clearly.
- **Modularity:** NLP, retrieval, risk scoring, scheduling, and user interface should be separable components.
- **Maintainability:** code and configuration should be organised so individual components can be updated.
- **Error reporting:** failures should produce useful messages and not silently corrupt data.
- **Explainability:** recommendations should show the important factors and evidence behind them.
- **Data integrity:** original logs and decision history should not be silently lost or overwritten.
- **Privacy and access control:** sensitive operational information should be protected according to the deployment's requirements.

Specific response-time, availability, and accuracy targets still need to be defined and tested.

## 12. Important Design Decisions and Caveats

### Preserve the source

Always retain the original log, even after cleaning or extracting it. This allows a user to check whether an extracted field is supported by the source.

### Human review is important

NLP extraction can be wrong, especially with abbreviations, ambiguous equipment names, negation, and incomplete sentences. Low-confidence fields should be reviewable.

### Keep evidence with recommendations

A risk or priority output should not be an unexplained number. Where possible, show contributing factors and links to relevant historical cases.

### Distinguish risk from scheduling feasibility

A high-risk issue may be difficult to schedule because a required technician or spare part is unavailable. The system should make this conflict visible instead of quietly lowering the issue's priority.

### Avoid unsupported certainty

If there are few historical examples or missing fields, indicate that the assessment is uncertain. A model should not be treated as reliable merely because it produces a score.

### Keep the decision human-controlled

The system can recommend and organise work, but the responsible maintenance user should retain control of approval and action.

## 13. Practical Implementation Order

A dependency-aware implementation sequence could be:

1. **Application foundation:** create the project structure, backend, frontend, configuration, and basic error handling.
2. **Database and access control:** establish the database schema and user permissions.
3. **Log ingestion:** upload, validate, identify, and preserve original logs.
4. **Structured record schema:** define equipment, component, symptom, action, date, and outcome fields.
5. **Basic NLP:** extract a small set of fields and show them beside the source text.
6. **Human review:** support correction and persist reviewed values.
7. **Terminology normalisation:** manage common abbreviations and synonyms.
8. **Historical case search:** implement a simple baseline search, then consider embeddings/vector search if needed.
9. **Knowledge relationships:** link equipment, components, symptoms, actions, and cases.
10. **Risk baseline:** define a transparent initial scoring method and evaluate it against appropriate historical outcomes.
11. **Priority recommendations:** add a documented, explainable priority policy.
12. **Resource management:** model technicians, skills, availability, parts, and durations.
13. **Scheduling:** propose schedules while enforcing relevant constraints.
14. **Dashboard and notifications:** surface records, pending review, recommendations, and alerts.
15. **Audit trail:** record decisions and changes with user and timestamp.
16. **Integration and testing:** verify the complete flow, error cases, access permissions, data integrity, and quality of recommendations.

The order can change as implementation constraints become clearer. Avoid building complex prediction or scheduling logic before the necessary data is available and reliable.

## 14. Testing Strategy

### Log ingestion

- Valid file or text is accepted.
- Invalid format is rejected with a useful error.
- Duplicate handling behaves as intended.
- Original content remains retrievable.
- Interrupted or malformed uploads do not create misleading complete records.

### NLP extraction

- Correctly identifies common equipment names and IDs.
- Extracts symptoms and actions.
- Handles missing fields.
- Does not misinterpret negation.
- Shows source evidence.
- Allows corrections to persist.

### Historical retrieval

- Relevant cases rank above unrelated ones in a reviewed test set.
- Filters return the expected records.
- No-match behaviour is clear.
- Search results link to their source records.

### Risk and priority

- Results use the expected inputs.
- Missing data is handled explicitly.
- Explanations correspond to the calculation or model.
- Performance is evaluated against labelled historical outcomes where available.
- The interface distinguishes an estimate from a confirmed failure.

### Scheduling

- Does not assign a technician to conflicting jobs.
- Checks required skills and resource availability.
- Handles unavailable spare parts.
- Reports infeasible schedules clearly.
- Preserves human approval of the final schedule.

### Audit and security

- Approval, modification, and rejection are recorded.
- Original and revised recommendations can be distinguished.
- User and timestamp are captured.
- Users cannot perform actions outside their permissions.
- Failed operations do not silently corrupt records.

## 15. What Is Known About Implementation Status?

The design description establishes the intended architecture and behaviour. It does **not**, by itself, prove that the modules have already been coded or integrated.

Until the repository and running application are inspected, treat these as **unverified implementation status**:

- Frontend and dashboard.
- Backend APIs.
- Database schema and persistence.
- NLP extraction.
- User review and correction.
- Knowledge graph or relationship layer.
- Historical similarity search.
- Risk model or scoring method.
- Priority recommendation logic.
- Resource-aware scheduler.
- Notifications.
- Decision/audit history.
- End-to-end integration and evaluation.

A feature should be marked “implemented” only after checking the code and, ideally, testing its behaviour. A useful status table during development is:

| Feature | Status | Evidence / test |
|---|---|---|
| Log upload and storage | Not yet verified | Link code and test result |
| NLP extraction | Not yet verified | Example input/output and extraction test |
| Human review | Not yet verified | Demonstrate edited fields persist |
| Historical search | Not yet verified | Retrieval test cases |
| Risk assessment | Not yet verified | Method, test data, and evaluation |
| Priority recommendation | Not yet verified | Rules/model and example explanation |
| Scheduling | Not yet verified | Resource-conflict tests |
| Dashboard | Not yet verified | Demonstrable UI flow |
| Notifications | Not yet verified | Trigger and delivery test |
| Audit trail | Not yet verified | Approval/change history test |
| Full integration | Not yet verified | End-to-end test |

## 16. Short Summary

The system is intended to transform maintenance notes into structured records, connect those records to equipment and past incidents, retrieve relevant cases, estimate risk, recommend priorities, and help create feasible maintenance schedules. It then presents the evidence to maintenance personnel, who make the final decision. The application should preserve original logs, expose uncertainty, and maintain an audit trail so recommendations and decisions remain traceable.

**Key principle:** the system should make maintenance information easier to use and decisions easier to justify—not hide uncertainty or replace the responsible human decision-maker.

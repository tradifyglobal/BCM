# Continuity360

Commercial BCM product in development, built as a Frappe application.
This is the **initial Phase 1 implementation**, not a production-ready SaaS release.

## Roadmap

**Phase 1 (BCM foundation) - functionally complete.** All modules are built, verified
on UAT and shipped in image `continuity360:phase1-20261117d`: organisation, risk,
BIA, BCP with versioning/distribution/acknowledgement, disaster recovery, testing &
exercises with corrective actions, call trees with span-of-control guidance,
compliance register, dashboards, Department View and the Report Centre with versioned
professional PDF reports. Remaining Phase 1 work is verification/hardening only:
full BCP approval browser journey (all four reviewer stages clicked through),
compliance register create/edit browser journey, real SMTP delivery and reminder
concurrency, a restore drill of a current release backup, an upgrade rehearsal and
automated release asset versioning.

**Phase 2 (operational modules) - implemented.** All four modules are built, verified
on UAT and shipped in image `continuity360:phase2-20261120`:
1. Incident Management: incidents with type, severity, lifecycle statuses, escalation
   chains, timelines (status changes are logged automatically), links to processes,
   risks, plans and call trees, and in-app alerts to the incident manager and
   escalation chain for high and critical severities.
2. Crisis Management: crisis events with levels, a named commander and deputy
   (must differ), triggering incident, activated BCPs/recovery plans and call tree,
   a decision/action log, communications issued per audience and channel, and
   standing communication plan templates. Standing down requires a timed outcome.
3. Application & Infrastructure Inventory: applications (criticality, hosting,
   vendor, recovery plan, supported business processes), servers, database instances
   and a typed dependency map (runs on / stores data in / integrates with) with
   exactly-one-target validation.
4. IT Infrastructure Recovery Intelligence (differentiator): a Recovery Intelligence
   page that simulates a component outage and walks through six steps - incident
   detected, business impact (affected applications through the dependency graph,
   processes, departments), plan activation (BCPs and call trees), recovery runbooks
   with RTO/RPO, validation guidance and a saved post-incident simulation record.
   Illustrative workflow over recorded relationships; no live cloud connections.

**Phase 3 (commercial SaaS layer) - implemented.** Shipped in image
`continuity360:phase3-20261120`:
1. Subscription management: Starter / Professional / Enterprise plans with per-module
   entitlements enforced server-side, seat licensing, expiry fallback to Starter and
   an operator-only plan store; tenants see their plan but cannot change it.
2. Central tenant administration: `scripts/tenant_admin.py` lists tenant sites and
   shows or sets each tenant's plan from the host, on top of the existing
   provisioning, isolation-drill and restore tooling.
3. White labelling (Enterprise): tenant display name, primary colour and report
   footer applied to desk navigation and all PDF reports.
4. API integrations (Enterprise): per-provider connection registry (AWS, Azure,
   Microsoft 365, monitoring) with encrypted credential storage and a normalized
   inventory import that upserts applications, servers and databases into the
   Recovery Intelligence graph. Live polling remains roadmap work.

**Remaining pre-launch gates.** Subscription billing/payments, a verified public
multi-tenant gateway, browser E2E and registry publishing in CI, concurrency testing,
an independent security assessment and a slimmer base image without ERPNext.

### Current verification status

Local checks passed: 7 domain tests, Python syntax, JavaScript syntax, JSON/TOML/YAML
parsing and development Compose isolation assertions. An isolated development stack
has been built and started on UAT. Four Frappe/MariaDB integration tests passed,
including company-scoped access and independent plan approval; authenticated PDF
generation and anonymous API denial were verified over HTTP. Browser checks exercised
the dashboard, navigation layouts, a risk-list link, search, notifications and an
authenticated realtime connection. A manual browser journey created and linked a
company, department, business process, risk and impact assessment, checked calculated
scores and dashboard results, and removed its test records. A recovery-plan browser
journey verified that the author could not approve their own plan, a separate reviewer
could approve it, and the approved plan could be retired. Its test records and reviewer
were removed. A disposable two-site drill verified separate databases, credentials,
sessions, files and background jobs, both directly against the internal Frappe backend
and through a test-only internal gateway. The test sites were removed afterwards.
The actual UAT frontend and a public multi-tenant gateway remain unverified for
tenant routing and file isolation. The disposable drill also exercised an operator-only
site-creation building block. The compliance control register passed a disposable
Frappe/MariaDB permissions test and was deployed to UAT. Its list and unsaved form
were checked in the browser; a complete browser create/edit journey remains unverified.
A later UAT dashboard update was checked in the browser with the blue theme, chart
empty states, navigation layout options and realtime connection. The risk-rating and
process-criticality charts also passed permission and aggregation tests in a
disposable Frappe/MariaDB stack. UAT had no risk or process records to chart.
The expanded BCP implementation has been deployed to UAT after verified database and
site-file backups. Nine disposable Frappe/MariaDB integration tests passed, covering
BCP approval, distribution eligibility, recipient-only snapshot access, open tracking,
acknowledgement and review reminders; eight domain-rule tests also passed. UAT
post-deployment checks passed for migration, health, the BCP DocTypes and frontend
assets. The browser verified the separate BCP/DR navigation, BCP dashboard and new
plan form without saving test data.
The subsequent versioning/PDF/DOCX increment is also deployed to UAT. Ten disposable
Frappe/MariaDB integration tests and ten focused domain tests passed on the final
candidate. A disposable browser scenario exercised author distribution, recipient
snapshot access, PDF/DOCX responses, acknowledgement persisted across reload, and
unrelated-user denial. It also exercised retirement and the author's Create
amendment action, saving and reloading version 1.1. Approval of the initial fixture
was performed by the workflow API, not by clicking through all approval stages.
No synthetic plans or recipients were added to UAT. UAT checks confirmed the new
fields/actions, working dashboard, stylesheet responses, realtime connection and
health. The running backend/frontend match image `continuity360:phase1-20261117d`,
which contains every in-place UAT hot-fix (schema reason field, scale pickers and
risk matrix, versioned asset URLs, Department View, Report Centre, the PDF report
engine with document control and the C360 Report Issue DocType) plus the Testing &
Exercises module and call trees with span-of-control warnings that complete the
Phase 1 functional scope. The image deploy
was preceded by verified database and site-file backups, ran migrations through the
standard configurator/create-site flow, and post-deploy checks confirmed the image
identity, demo-data counts, desk pages, asset responses and report generation.
Full approval-stage browser journeys and a separate upgrade rehearsal remain
unverified; this is not yet an enterprise-ready BCP module.
A persistent GeeksOnTap demo dataset was later seeded into UAT at the customer's
request (departments, employees, risks, BIA, approved DR and BCP plans, a tracked
distribution and compliance controls), with a configured outgoing/incoming email
account. Demo seeding surfaced a defect: the stored distribution recipient reason
was a 140-character Data field, but combined eligibility reasons can exceed that.
The field is now Small Text in `schema.py`. The fix was first applied in place to the
UAT DocType metadata and container and now ships in image `continuity360:phase1-20261117`.
A UAT backup was restored into a separate disposable stack; its 14
Continuity360 tables matched UAT at comparison time (one company record and no other
domain records). The file archives contained no user files, so file-content restoration
for that UAT backup remains unverified. A separate disposable drill restored sample
public and private file contents. This is not a production-ready deployment.

## Phase 1 implementation

- Organisation: companies, departments, locations, employees and vendors.
- Risk register: server-calculated 5-by-5 inherent scoring, residual assessments and treatments.
- BIA: critical business processes, four impact dimensions, RTO, RPO and MTPD in minutes.
- Continuity: recovery strategies, ordered procedures, team contacts and controlled plans.
- BCP module (deployed to UAT): separate plans with business units, continuity
  strategies, teams, contacts and procedures, plus same-company recovery-plan links.
  Named authors, manager reviewers, BCM reviewers and executive approvers use separate
  review stages. Four distinct users are required and the review date must be no more
  than one year after approval. A BCP overview counts visible plans, approval-stage
  plans, upcoming or overdue reviews, plans tested and completed exercises over the
  last 12 months, and open corrective actions. Role and company permissions still apply to links.
  At approval, a permission-filtered snapshot preserves linked records and contact
  details; normal links continue to show current records. Changes to linked records
  during review require the plan to return to draft and be reviewed again. The
  approved-snapshot button and dashboard were checked in a disposable browser session.
  A daily job creates review notifications for eligible plan owners at 30, 7 and 1
  days before review and weekly when overdue; missed runs catch up within the current
  interval. In-app and email notification preferences apply. Email also requires
  configured outbound mail, and a queued message does not establish delivery.
  Existing users may need to enable the new BCP Review email type in their
  notification settings. Reminder concurrency and real email delivery have not yet
  been tested.
  Approved-only distribution is implemented for stakeholders identified by the plan;
  the plan owner or a BCM Administrator may select recipients. Each recipient opens
  the approval-time snapshot through a sign-in-required page, with open timestamps,
  repeat-open count and explicit acknowledgement recorded per recipient. Distribution
  unit/integration behavior and the disposable browser recipient journey are tested.
  Server-assigned plan versions are deployed to UAT: new plans start at
  1.0; choose Minor (1.1) or Major (2.0) before first saving an amendment. Version,
  revision type and predecessor are immutable after that save. Retire the existing
  plan before using Create amendment (Frappe's built-in Amend action); each predecessor permits one successor,
  and every successor must complete the full approval workflow. This means the old
  plan is not active while its replacement is reviewed. Legacy plans and approval
  snapshots are not rewritten; unnumbered legacy predecessors use 1.0 as their
  amendment baseline, and their exports are labelled unnumbered.
  Approved and retired snapshots can be downloaded as PDF or Word (DOCX), either
  from the plan form (read and print permission required) or by an addressed
  recipient from the secure distribution page. Downloads apply the same current
  field-level and linked-record permissions as the snapshot view. Rich text is
  exported as plain text, with ordered child rows; images and attachments are not
  embedded. No download is a read acknowledgement. Copies include the version,
  approval capture date, requesting user/time and current status; retired plans are
  marked historical. Offline copies are uncontrolled and cannot be revoked.
  The disposable browser verified both download formats and recipient acknowledgement.
  Assign the BCP
  Author, BCP Manager Reviewer, BCM Administrator and BCP Executive Approver roles to
  the corresponding named users; the assigned author also needs access to any recovery
  plans they link.
- Testing & Exercises: tabletop exercises, walkthroughs, simulations, DR drills and
  full interruption tests, each with a scenario, objectives with assessed outcomes,
  participants, overall result, achieved recovery time, results summary and lessons
  learned. Completing an exercise requires the conducted date, an overall result, a
  results summary and an assessed outcome for every objective. Corrective actions link
  to an exercise with priority, owner, due date and status; completion requires
  recorded evidence and stamps the completion date. Exercises may link a business
  continuity plan and/or a recovery plan from the same company. Editable by Risk
  Managers, IT Managers and BCP Authors; readable by auditors and BCP reviewers. The
  BCP dashboard shows plans tested and completed exercises over the last 12 months and
  open corrective actions, and the Report Centre includes a Testing and Exercise
  Report plus a Testing and Exercises chapter in the combined report. Verified on UAT:
  13 domain tests (including exercise completion rules), dashboard counts, navigation,
  list rendering, report PDFs and the server-side completion guard. GeeksOnTap demo
  data includes two completed exercises, one planned walkthrough and two corrective
  actions (one open, one completed with evidence).
- Call trees: emergency notification cascades built from emergency contacts, recording
  who calls whom, each member's cascade role, and activation criteria and caller
  instructions. Structural validation always rejects duplicate contacts, self-calls
  and callers who are not members; setting a tree Active additionally requires at
  least two members, an initiator and every member reachable from an initiator (no
  cycles or orphans). The form shows a live indented cascade preview with phone
  numbers and flags unreachable members. Only Active (completed) call trees print in
  documents: the BCP report and the combined report include a Call trees section with
  the cascade hierarchy, roles, responsibilities, phone, email and who each person
  calls. Trees may link a business continuity plan and/or department and follow that
  scope in department-filtered reports. Editable by BCP Authors and IT Managers.
  Verified on UAT: 17 domain tests (4 call-tree structure cases), server-side
  activation guard, form preview in the browser and PDF rendering. The GeeksOnTap
  demo includes an Active seven-member cascade linked to the corporate BCP, plus IT
  and Finance department call trees whose leads cascade from the corporate tree
  (the recommended two-level pattern). Callers phoning more than seven people trigger
  a non-blocking span-of-control warning on save, in the form preview and as a note
  in printed reports; ISO 22301 clause 7.4 is tool-agnostic about notification
  methods, so the three-to-seven band is applied as good practice, not compliance.
- Governance: BCM Administrator, Risk Manager, IT Manager, Auditor and Employee roles.
- Approval: Draft -> In Review -> Approved -> Retired. Approval requires a different person
  from the author. Approved plans are submitted documents; revisions require amendment.
- Frappe change history plus mandatory revision reasons for recovery-plan content changes.
- Compliance control register with customer-entered framework references, self-assessed
  status, owners and evidence references; no standards content is supplied.
  ISO 22301:2019/Amd 1:2024 (February 2024) added two clause 4 requirements: the
  organisation shall determine whether climate change is a relevant BCMS issue (4.1)
  and interested parties can have climate-related requirements (4.2). Continuity360
  accommodates this through the Environmental risk category and a customer-entered
  compliance control evidencing the documented climate-relevance determination; the
  GeeksOnTap demo includes such a control alongside its flood and power-failure risks.
- Permission-aware dashboard with risk-rating and process-criticality charts, risk
  heatmap and management PDF endpoint. Charts use visible records, not sample data.
- Report Centre page with a single department selector that scopes every report, six
  detailed server-generated PDF reports (BIA, risk assessment, BCP, DR, testing and
  compliance) and a combined Business Continuity Management report with numbered
  chapters covering all six areas. Every PDF page carries the report name and department scope in the
  header and "Page N of M" in the footer. Risk and DR reports scope through the
  department's business processes (risks without a linked process are excluded when a
  department is selected); BCP scopes by covered business units; the testing report
  scopes to exercises whose plan covers the department or recovers one of its
  processes; compliance controls
  are organisation-wide and are labelled accordingly. Reports include only records
  visible to the requesting user, render rich text as plain text and are labelled as
  uncontrolled copies. Reports are branded with the customer's company name when the
  requesting user sees exactly one company (the tenant norm), with a small "Generated
  by Continuity360" attribution; multi-company viewers fall back to product branding.
  Professionally styled PDFs: cover page (brand bands, title, scope pill, metadata table
  with prepared-for/classification and a human-readable generation timestamp), table of
  contents, navy striped tables with fixed layout and word wrapping so content never
  crosses the page margin, and colored badges for likelihood, impact, scores, risk
  ratings, statuses, criticality and RTO/RPO/MTPD targets. Visual rendering, cover
  content, badge colors and absence of table overflow were verified against UAT.
  Document control: every generated report is logged in the system-managed C360 Report
  Issue DocType and receives an auto-incrementing issue version per report and
  department scope. The cover shows the document version, prepared-by (full name and
  account) and a document history table of recent issues; the footer carries the
  version on every page. BCP and DR reports include a "Document control and approvals"
  section naming who prepared each plan, the manager/BCM reviewers, the executive
  approver and who approved it when; BIA and risk details name the record owner, who
  entered it and who last updated it. User accounts are rendered as full names
  throughout the reports.
- Clickable colored rating scales on editable forms: 1-5 likelihood/impact pickers on
  risks, residual assessments and BIA impact dimensions, and preset duration pickers
  for RTO/RPO/MTPD. Clicking sets the underlying field; typed values remain supported,
  presets highlight only on exact matches, and submitted or read-only documents show
  the scales disabled. Implemented in `scale_picker.js`; initially hot-deployed to UAT
  and now shipped in image `continuity360:phase1-20261117`.
- Top dropdown navigation, left sidebar or both; preference saved per browser/user.
- Department View page (Organisation menu): choose a department from a dropdown and see
  its BIA processes, impact assessments, risks, residual assessments, treatments, BCPs,
  DR plans and employees on one screen, each row linking to the record and each section
  respecting the viewer's role permissions. Supports `?department=` links.
- Reproducible, localhost-only Docker development stack and GitHub Actions validation.
- Documentation: `docs/Continuity360-User-Guide.pdf` is a 26-page illustrated,
  step-by-step user guide covering the complete BCM cycle across all three phases,
  written for novice users with 17 annotated screenshots of the GeeksOnTap demo.
  Source: `docs/guide/user-guide.html` plus `docs/guide/shots/`; rebuild by replacing
  the image placeholders with base64 data URIs and rendering with wkhtmltopdf.

## Phase 2 implementation

- Incidents: recorded with type, severity (Low to Critical), status lifecycle
  (Open/Investigating/Mitigated/Resolved/Closed), reporter, incident manager,
  detection and resolution times, impact, root cause, and links to the affected
  business process, related risk, activated recovery plan/BCP and call tree used.
  Escalation chains name who is escalated to at which level and on what criteria;
  escalation levels must be unique. Timelines record detection, escalation, actions,
  communications and resolution; a Status Change entry is appended automatically
  whenever the status changes. Resolving or closing requires a resolution time after
  detection and a resolution summary. Creating a High or Critical incident raises
  in-app alerts for the incident manager and everyone on the escalation chain.
  Editable by IT Managers and Risk Managers.
- Crisis events: levels 1-3, status Declared/Managing/Stood Down/Closed, a required
  crisis commander and optional deputy (must be different, enabled users), the
  triggering incident, activated BCPs and recovery plans, the call tree activated,
  a decision/action log (status changes logged automatically) and communications
  issued per audience/channel with responsible owner and sent time. Standing down or
  closing requires a stand-down time after declaration and an outcome summary.
  Standing communication plans hold pre-approved audience/channel templates with
  triggers, owners and approvers. Editable by Risk Managers.
- Infrastructure inventory: applications (criticality, hosting model, vendor,
  recovery plan, supported business processes), servers (environment, platform,
  location, OS), database instances (engine, platform, hosting server) and typed
  dependencies (runs on / stores data in / integrates with / supplied by) that name
  exactly one target component and never the application itself. Editable by IT
  Managers; company-link integrity enforced throughout.
- Recovery Intelligence: the Recovery Intelligence desk page simulates an outage of
  any application, server or database and renders the six-step walkthrough from the
  product vision - incident detected, business impact analysis (affected applications
  resolved through the dependency graph including downstream integrations, business
  processes, departments), recovery plan activation (covering BCPs and Active call
  trees), recovery procedures with RTO/RPO targets, validation guidance and a
  post-incident record. Every simulation is stored as an Outage Simulation document
  with the full walkthrough JSON. Clearly labelled illustrative: it reasons over
  recorded relationships, with no live infrastructure connection.
- Reporting: two new PDF reports (Incident and Crisis Report; Infrastructure and
  Recovery Intelligence Report) with the same professional styling, department
  scoping, badges and document control as Phase 1; the combined BCM report now has
  eight chapters. The management dashboard adds open-incident and active-crisis
  metrics. Navigation gains Incident & Crisis and Infrastructure groups (top bar and
  sidebar).
- Verification: 25 domain tests pass (incident lifecycle, crisis closure, dependency
  target rules); server-side guards verified for incident resolution and dependency
  targets; alert creation verified for a Critical incident; the auto-appended
  status-change timeline verified; all three new report PDFs text-verified; the
  Recovery Intelligence page exercised in the browser end to end, correctly walking
  a database outage through downstream applications to departments, plans, call
  trees and runbooks. GeeksOnTap demo data now includes three applications, two
  servers, two databases, five dependencies, a resolved Critical incident with
  escalations and timeline, an open Medium incident, a closed Level 2 crisis with
  log and communications, two standing communication plans and saved outage
  simulations.

## Phase 3 implementation

- Subscription management: the operator-managed C360 Subscription single stores the
  plan (Starter/Professional/Enterprise), licensed seats, validity date and customer
  reference. Tenant roles can read it; only the operator changes it via
  `bench execute continuity360.subscription.set_plan` or `scripts/tenant_admin.py`.
  Entitlements: Starter covers the full BCM foundation (organisation, risk, BIA,
  BCP, DR, call trees, testing, compliance, reports); Professional adds Incident &
  Crisis Management; Enterprise adds Infrastructure & Recovery Intelligence, white
  labelling and API integrations. Enforcement is server-side on record creation in
  gated modules with a clear upgrade message, and the navigation hides gated groups.
  An expired subscription falls back to Starter entitlements and is flagged in the
  sidebar. Seat licensing blocks enabling a System User beyond the licensed count
  (role-less Website Users without desk access do not consume seats). Sites without
  a configured plan run as Enterprise for development; provisioning must set a real
  plan. The whitelisted status endpoint reports plan, modules, seats and branding.
- Central tenant administration: `python3 scripts/tenant_admin.py list|show|set-plan`
  on the Docker host enumerates tenant sites and manages each tenant's subscription
  through bench, keeping tenant databases isolated.
- White labelling (Enterprise): the C360 Branding single holds a display name,
  six-digit hex primary colour (validated and normalised) and a report footer line.
  Branding themes the desk navigation (brand name, top bar and accents) and every
  PDF report (brand name, retinted headings and tables, attribution footer).
  Saving branding on a non-Enterprise plan is rejected, and lower plans
  automatically render the default Continuity360 identity.
- API integrations (Enterprise): C360 Integration Connection registers AWS, Azure,
  Microsoft 365 or monitoring accounts with a non-secret account reference, an
  encrypted credential slot and an enabled flag. The whitelisted
  `continuity360.integrations.import_inventory` endpoint accepts a normalized JSON
  payload (for example derived from `aws ec2 describe-instances` or `az vm list`)
  and upserts applications, servers and database instances with provider-appropriate
  platforms, stamping the connection's last import time. Live credential-based
  polling is roadmap work and is labelled as such.
- Public presence: guests at the site root see a professional marketing landing page
  (hero, module grid, BCM cycle, Recovery Intelligence spotlight, compliance strip,
  plan tiers and a demo-request call to action) with the developer credit
  "Developed by : Fayazuddin Zubair Mohammed" in the footer. /login is a branded
  "Login to Continuity360" card replacing the Frappe default; it accepts an email or
  a plain username (so Administrator can sign in), posts to the standard login API,
  sanitises redirect targets, offers password reset and carries the same footer
  credit. Signed-in users visiting either page are redirected to the workspace. An
  Administration navigation group exposes Users, Subscription and Branding to
  authorised roles; the tenant administrator holds System Manager and creates users
  and sets their passwords from the Users list, subject to seat licensing. A
  read-only demo account exists for public demonstrations.
- Verification: 30 domain tests pass (plan entitlements, expiry fallback, seat
  limits, brand colour validation). A live UAT drill confirmed Starter blocks
  incident and infrastructure creation, Professional allows incidents but not
  infrastructure, an expired Enterprise plan falls back to Starter with an expiry
  message, seat enforcement blocks an over-limit System User, branding is applied
  to reports (retinted PDF, footer line, brand name) and navigation (GeeksOnTap
  name, themed top bar, plan badge), gated navigation groups disappear on Starter
  and return on Enterprise, and an AWS connection import created two inventory
  records, updated one and skipped an invalid row. The GeeksOnTap tenant runs
  Enterprise (25 seats, valid until 2027-12-31) with an AWS production connection.
  White labelling was verified end to end and then cleared at the customer's request:
  the tenant uses the default Continuity360 identity (navy-blue theme, Continuity360
  navigation brand), and reports brand with the company name as before. Reverting the
  branding record restores the defaults with no code change, which is itself the
  intended downgrade behaviour.

DocTypes use the `C360` prefix to avoid collisions with ERPNext/HRMS. They are defined in
`continuity360/schema.py` and synchronised as app-owned custom DocTypes during installation
and migration. This avoids enabling developer mode on tenant sites. Do not edit these
definitions through Customize Form: changes to owned metadata are replaced on migration.
The recovery-plan workflow is created once and then preserved on migrations.

No sample customer data or fabricated health metrics are loaded. The dashboard shows
actual records visible to the current user. Future infrastructure functionality is
explicitly labelled as roadmap work; no live cloud connections or recovery execution exist.

## Development setup

Requires Linux, Docker Engine and Docker Compose v2. The image is based on the official
`frappe/erpnext:v16.55.0` runtime (Frappe 16 / Python 3.14). ERPNext is present in the
base image but **is not installed** on the Continuity360 site. A slimmer standalone
Frappe image should be evaluated before commercial distribution.

Run these commands on the dedicated development host from the project directory:

```bash
python3 scripts/create_dev_secrets.py
docker compose config --quiet
docker compose build backend
docker compose up -d --wait --wait-timeout 600
docker compose ps -a
curl --fail http://127.0.0.1:18080/api/method/ping
```

Services use the `continuity360-dev` Compose project, a separate bridge network and
named volumes. Only `127.0.0.1:18080` is published; MariaDB and Redis have no host ports.
There are no Kubernetes operations in this setup. Resource ceilings are for a small
development VM, not production sizing. Building images also consumes CPU, RAM and disk.
The development-only site setup uses Frappe's setup wizard with English, Canada, CAD
and UTC as changeable development defaults. It does not create a named user.

On Windows, with the local untracked SSH configuration:

```powershell
ssh -F C:\BCM\ssh_config -N -o ExitOnForwardFailure=yes -L 18080:127.0.0.1:18080 continuity360-uat
```

Keep that terminal open, then visit `http://localhost:18080/desk/continuity360`.
If the terminal or SSH process exits, this local URL stops working even when the
remote application is healthy.

For automatic reconnection and startup at Windows sign-in, close the manual tunnel,
then run these commands as the Windows user who owns the existing SSH key:

```powershell
& C:\BCM\scripts\Install-UatTunnel.ps1
Start-ScheduledTask -TaskName Continuity360-UAT-Tunnel
curl.exe --fail http://127.0.0.1:18080/api/method/ping
```

The task runs without elevation or stored passwords and only while that user is
signed in. It uses the repository's existing `ssh_config`, strict host-key checking
and key authentication. The supervisor retries every five seconds after SSH exits;
keepalives detect broken connections after approximately 90 seconds, followed by
connection timeout/retry time. It does not expose a public server port or fix a
remote application outage. Do not start a second manual tunnel on the same port.
Keep this checkout at its registered path, or reinstall the task after moving it.
Windows execution policy and organizational Task Scheduler permissions still apply;
the installer does not change or bypass them.

Logs are at `%LOCALAPPDATA%\Continuity360\uat-tunnel.log` (one rotated copy retained).
To disable automatic access, stop and remove the task:

```powershell
Stop-ScheduledTask -TaskName Continuity360-UAT-Tunnel
Unregister-ScheduledTask -TaskName Continuity360-UAT-Tunnel -Confirm:$false
```

Log in as `Administrator`. Retrieve the generated development password **locally on
the server** from `.secrets/admin_password`; do not paste it in chat or commit it.
Create named users and assign appropriate roles before entering records. Give plan
authors IT Manager and independent reviewers BCM Administrator. Administrator is a
technical superuser, not a substitute for application-level separation of duties.

Secret files are generated once, never printed, ignored by Git and excluded from image
builds. Only the one-shot site setup starts as root to read host-owned Compose secrets;
it drops to the image's `frappe` user before site setup and passes creation passwords
to Frappe in-process rather than as command-line arguments. Frappe still stores the
site's database credentials in its configuration, and privileged host or container
access can expose secrets. Application processes run as `frappe`. Never add SSH
passwords, private keys or production credentials to this repo.

The development image configures realtime authentication to reach the internal backend
and uses WebSocket-only transport; networks that block WebSockets will not receive
realtime updates. The proxy preserves the browser's Origin for Frappe's origin check.
The pinned base image's `frappe` user has the `root` group; the application copy uses
that existing group. These image-specific changes must be revalidated when upgrading
Frappe.

### Public demo hosting (bcm.geeksontap.ca)

The UAT stack is published as a public demo at `https://bcm.geeksontap.ca`:

- `publish-lan.yaml` additionally publishes the frontend on `192.168.50.30:18080`
  for the reverse proxy. Apply it with every compose operation on UAT:
  `docker compose -p continuity360-dev -f compose.yaml -f publish-lan.yaml up -d`.
  Deploys that omit it will recreate the frontend without the LAN binding and take
  the public demo offline (localhost access keeps working).
- The nginx reverse proxy on 192.168.50.21 terminates TLS
  (`/etc/nginx/sites-available/bcm.geeksontap.ca`): HTTP-01 ACME webroot at
  `/var/www/certbot`, HTTP to HTTPS redirect, websocket upgrade headers and
  `X-Forwarded-Proto https`, proxying to `http://192.168.50.30:18080`. The container
  nginx pins `FRAPPE_SITE_NAME_HEADER`, so the public hostname serves the site
  without a Frappe site rename; the site's `host_name` is set to the public URL.
- The certificate is from Let's Encrypt (expires 2027-02-19) and renews through the
  standard `certbot.timer`; renewals only need port 80 to stay forwarded to the proxy.
- This is a demo exposure of a development-grade stack: the pre-launch gates
  (independent security assessment, concurrency testing, public multi-tenant gateway
  validation) remain outstanding, Docker's published port bypasses host firewalls on
  the LAN segment, and demo credentials should be rotated if shared externally.

### Updating an existing development deployment

Back up the site and database first. Copy the new source, rebuild the image, then:

```bash
docker compose build backend
docker compose stop backend frontend websocket worker scheduler
docker compose run --rm configurator
docker compose run --rm create-site
docker compose up -d --wait --wait-timeout 600
```

After an image change, clear the affected site's Frappe cache with
`bench --site <site-name> clear-cache` inside the backend container, then reload Desk
and check that the requested Frappe CSS bundles return `200` with `text/css`. Existing
browser pages can retain old asset mappings; a full browser reload may be necessary.
Continuity360's custom CSS and JavaScript currently use unversioned URLs, so browser
cache invalidation across releases is not automated; use a hard reload if changes do
not appear. Release-safe asset versioning remains production work.

An existing site's migrations are run, not skipped. If installation previously failed
partway through, setup fails visibly; inspect the cause rather than deleting volumes.
Do not run `down -v` on data you want to retain. This development setup does not implement
automatic production upgrades, backup retention or rollback. The tested Frappe version's
standard database backup and restore commands pass the site database password as a process
argument. The isolated restore drill uses a protected temporary client option file instead.
Review credential handling and rotate potentially exposed credentials as appropriate before
using standard commands on a shared host.

### BCP document-control approach

BCI's public [GPG 7.0 Lite](https://www.thebci.org/resource/good-practice-guidelines--gpg--lite-edition-7-0.html)
describes ongoing maintenance, review and improvement of continuity arrangements.
Its public overview does not establish a required numeric versioning convention
or a mandatory retire-and-amend workflow. Continuity360's major/minor numbering,
approval snapshots and download labelling are product design decisions, not a
claim of BCI certification or verified conformance with the full licensed GPG.

The versioning release's pre-migration logical database and site-files archives are
retained on UAT under
`/home/zubair/continuity360-dev/backups/bcp-versions-20261117T003331Z`.
Both archive integrity checks passed; this release's backup has not been restored
in a separate drill. The previous image is retained as
`continuity360:rollback-bcp-versions-20261116`. Image rollback alone does not undo
database migrations.

The phase1 image releases (`continuity360:phase1-20261117`,
`continuity360:phase1-20261117b` with Testing & Exercises,
`continuity360:phase1-20261117c` with call trees and
`continuity360:phase1-20261117d` with span-of-control warnings and department call
trees, all built from committed source via `git archive`) have pre-migration database
and site-file backups under
`/home/zubair/continuity360-dev/backups/phase1-20261117T050947Z`,
`/home/zubair/continuity360-dev/backups/phase1b-20261117T201822Z`,
`/home/zubair/continuity360-dev/backups/phase1c-20261118T001940Z` and
`/home/zubair/continuity360-dev/backups/phase1d-20261118T003117Z` with verified
checksums. The replaced images are retained as rollback-tagged copies
(`continuity360:rollback-phase1-20261117` through
`continuity360:rollback-phase1-20261117d`).
These releases' backups have not been restored in a separate drill.

The Phase 2 release (`continuity360:phase2-20261120`, built from committed source via
`git archive`) has pre-migration database and site-file backups with verified
checksums under `/home/zubair/continuity360-dev/backups/phase2-20261120T163102Z`;
the replaced image is retained as `continuity360:rollback-phase2-20261120`.
Post-deploy checks confirmed the image identity, all Phase 1 and Phase 2 demo data,
the desk pages and 26-page combined report generation.

The Phase 3 release (`continuity360:phase3-20261120`) has verified pre-migration
backups under `/home/zubair/continuity360-dev/backups/phase3-20261120T183200Z`; the
replaced image is retained as `continuity360:rollback-phase3-20261120`. Post-deploy
checks confirmed the image identity, the Enterprise subscription with GeeksOnTap
branding, seat usage and all demo data including the AWS integration connection.

The public-presence release (`continuity360:phase3-20261120c` with the landing page,
branded username-or-email login and Administration navigation) has verified backups
under `/home/zubair/continuity360-dev/backups/` with the `phase3b-`/`phase3c-`
prefixes and rollback-tagged predecessors. A first deploy attempt failed because
`dev_setup.initialize` rejected the public `host_name`; the guard now returns early
for completed sites and the deploy was repeated successfully. The Administrator
password was resynchronised with `.secrets/admin_password`.

## Testing strategy

This is a new mixed Desk UI/API application; there are no legacy test assets.

1. Domain tests: risk score boundaries, invalid inputs, recovery targets and treatment dates.
2. Real Frappe/MariaDB integration: persisted scoring, company-link integrity,
   independent approval, submitted-plan immutability and role/company-scoped reporting.
3. HTTP: readiness, unauthenticated API rejection, authenticated PDF generation.
4. Browser: login, organisation/risk/BIA/plan journeys and all three navigation modes.
5. Before SaaS launch: public tenant-routing and public-file isolation tests, expanded
   restore drills, upgrade rehearsal, concurrency and independent security assessment.
   The disposable internal gateway drill does not validate a public gateway.

```bash
python3 -m unittest discover -s tests -v
docker compose exec -T backend bench --site continuity360.localhost set-config allow_tests true
docker compose exec -T backend bench --site continuity360.localhost run-tests \
  --module continuity360.tests.test_phase_one
```

Use a disposable site for integration tests, not a customer site. Test records have unique
identifiers and roll back. Tests use real MariaDB/Redis; no SQLite substitute is claimed
to prove Frappe behavior. Without a running Frappe stack, only the domain tests and static
checks can run; database, permissions, workflow, PDF and browser behavior remain unverified.
The checked-in CI workflow runs domain/static checks, builds the image, starts the stack
and runs real-database tests. Browser E2E and registry publishing are not yet automated.

### Disposable backup/restore drill

On a Linux Docker host with the `continuity360:dev` image already built, run:

```bash
python3 scripts/restore_drill.py
```

The drill creates a unique Compose project with its own internal network, database,
Redis, volumes and generated credentials. It backs up and restores a disposable site
containing a company, risk, and public and private files, checks their restored content
and relationships, then removes only the drill's resources. No existing site or volume
is used. MariaDB credentials are supplied through a mode-0600 temporary client option
file in the container's memory-backed `/dev/shm`, not command-line arguments.

This is a development verification tool, not a production backup or restore service.
It does not implement offsite storage, encryption, retention, recovery of site
configuration, or scheduling. It requires the Frappe 16/MariaDB development image and
must be revalidated when that image changes.

### Disposable tenant isolation drill

On the same Linux Docker host and image, run:

```bash
python3 scripts/tenant_isolation_drill.py
```

The drill creates two sites in a separate disposable Compose project using the
site-creation entry point and separate generated administrator secrets. It checks private
file contents for identical paths, duplicate-site rejection, cross-site credential and
session rejection, guest denial, and
queued updates on a real shared worker using identical document IDs. It also checks
public and private file routing through a test-only internal Nginx gateway with two
allowlisted hostnames, including rejection of unknown hosts, direct protected paths
and spoofed tenant headers. Public files are accessible to anyone who knows their URL.
The gateway publishes no host ports and is not the UAT frontend or a production gateway.
The drill does not validate public routing, TLS, a dynamic hostname registry, tenant
provisioning, or isolation from a compromised worker or host. It removes the disposable
project and its volumes after the test.

### Tenant site creation building block

`scripts/provision_tenant_site.py` creates a new Frappe site with the Continuity360 app
and refuses existing site paths. It uses a nonblocking, cooperative file lock in the
shared sites directory to prevent simultaneous creation by this tool. The lock file
remains in place; an interrupted process releases its lock, not the file. The two-site
drill exercises its entry point against disposable databases. The operator-only entry point expects a trusted setup
container, a lowercase DNS hostname argument, and separate mounted
`/run/secrets/db_root_password` and `/run/secrets/tenant_admin_password` files. It
drops to the `frappe` user before site creation and does not print passwords.

This is not a production provisioning service: the lock only coordinates processes using
this tool and depends on filesystem lock semantics; other provisioning methods and
distributed deployments are not covered. There is no control plane, tenant registry,
routing activation, distributed coordination, retry/reconciliation, credential delivery,
billing or offboarding. A failed Frappe
installation can leave a partial site and database; inspect them rather than retrying
or deleting data automatically. Do not run this building block against customer sites
or expose it as an API. The UAT deployment has not been changed to use it.

## Tenant and security boundaries

- One Frappe site per customer, with separate databases, files and users.
- Multiple companies may exist **within** a customer's site. This is not tenant isolation.
- Roles define within-site access. Frappe User Permissions can additionally constrain Company.
  Directory access is intentionally more limited than general organisation access.
- The development frontend deliberately routes to **one fixed site**. It is not a public
  multi-tenant gateway. Commercial routing must validate hostnames against provisioned sites;
  never select a customer site using an untrusted forwarded header.
- Shared-site infrastructure does not isolate a compromised application worker or host.
  Regulated customers may require dedicated stacks, database credentials, storage and keys.
- Frappe Version records provide application change history, not immutable/WORM audit evidence.
- This repository does not establish ISO 22301 certification, SOC 2 assurance, data residency,
  enterprise readiness or a guaranteed recovery SLA.

## Product phases and remaining scope

Follow the supplied phase order; do not market future features as implemented:

1. **Foundation (in progress):** complete and validate BCM workflows/reporting, tenant
   lifecycle, central subscription/entitlements, backups/restores and initial ISO 22301
   mappings. The control register accepts customer-entered references, but does not supply
   framework mappings. These SaaS operations are not implemented by this initial slice.
2. **Operational resilience:** critical business services and dependency mapping.
3. **Infrastructure intelligence:** application, server, database, network and cluster inventory.
4. **DR intelligence:** incident impact simulation, runbooks, recovery execution tracking and validation.
5. **Integrations:** least-privilege Azure/AWS/M365 discovery, redacted Terraform import and monitoring.
6. **Compliance/governance:** licensed framework mappings, evidence lifecycle, SSO/MFA,
   enterprise audit controls, residency and private deployments.
7. **AI/automation:** reviewable assistance only after core data quality and governance.

Commercial architecture needs a separate SaaS control plane for billing, entitlements,
provisioning, upgrades, backup policy and support access. Do not use tenant-editable
subscription labels as billing enforcement. Provisioning must not be a public tenant API.
For production Kubernetes, use Frappe web/realtime/queue/scheduler components, migration Jobs,
managed or properly operated databases, tenant-aware storage, secret management and tested
region recovery. Kubernetes/Helm delivery follows validated Docker operation; this Compose
file is not represented as an enterprise HA architecture.

GitHub Actions is prepared, but no repository has been created/pushed and no registry or
deployment credentials are configured. Select the destination repository and release
approval policy before enabling publishing/deployment. Review Frappe, bundled ERPNext and
other dependency licences with qualified counsel before commercial distribution.

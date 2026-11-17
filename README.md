# Continuity360

Commercial BCM product in development, built as a Frappe application.
This is the **initial Phase 1 implementation**, not a production-ready SaaS release.

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
health. The running backend/frontend match image `continuity360:phase1-20261117b`,
which contains every in-place UAT hot-fix (schema reason field, scale pickers and
risk matrix, versioned asset URLs, Department View, Report Centre, the PDF report
engine with document control and the C360 Report Issue DocType) plus the Testing &
Exercises module that completes the Phase 1 functional scope. The image deploy
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
- Governance: BCM Administrator, Risk Manager, IT Manager, Auditor and Employee roles.
- Approval: Draft -> In Review -> Approved -> Retired. Approval requires a different person
  from the author. Approved plans are submitted documents; revisions require amendment.
- Frappe change history plus mandatory revision reasons for recovery-plan content changes.
- Compliance control register with customer-entered framework references, self-assessed
  status, owners and evidence references; no standards content is supplied.
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

The phase1 image releases (`continuity360:phase1-20261117` and
`continuity360:phase1-20261117b` with Testing & Exercises, both built from committed
source via `git archive`) have pre-migration database and site-file backups under
`/home/zubair/continuity360-dev/backups/phase1-20261117T050947Z` and
`/home/zubair/continuity360-dev/backups/phase1b-20261117T201822Z` with verified
checksums. The replaced images are retained as `continuity360:rollback-phase1-20261117`
and `continuity360:rollback-phase1-20261117b`.
These releases' backups have not been restored in a separate drill.

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

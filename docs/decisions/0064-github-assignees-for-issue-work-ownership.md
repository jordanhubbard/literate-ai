# ADR 0064: Use GitHub assignees as durable issue work ownership

- Status: Proposed
- Date: 2026-11-05
- Decision owners: Literate AI maintainers and the directing user
- Release target: 1.5.0 planning milestone
- Roadmap: pending explicit acceptance; requested by [issue #323](https://github.com/jordanhubbard/literate-ai/issues/323)

## Context

`litai project peer-work survey` finds related issues, reviews, branches and
worktrees, while branch lifecycle markers describe local or shared Git state.
Neither is a durable, cross-session claim on a GitHub issue. An agent can resume
on another machine or another member can start the same issue without seeing a
chat message or a local worktree. Issue #323 asks for the native GitHub assignee
field to be the shared authority for who is working on each issue.

GitHub's assignee update is not a compare-and-swap claim. A read, update and
readback can detect a competing claim, but it cannot reserve an issue against
future changes by another client. The workflow must state that limit honestly
and recheck ownership at meaningful boundaries.

## Proposed decision

For a GitHub-backed project, use the issue's current GitHub assignees as the
sole shared work-ownership record. Resolve the acting member from the
authenticated GitHub account used for the operation. A provider-supplied user
name, a local `--actor` string, a branch name, a worktree and a chat claim are
not substitutes for that identity or for the assignee readback.

Add an explicit issue-work operation to the `litai project peer-work` surface.
It reads the issue and authenticated account, rejects closed or unavailable
issues, and returns the observed assignees before any mutation. Starting an
unassigned issue requires an authorized GitHub assignee update to add that
account and a fresh readback that confirms the issue is open and assigned only
to that account. If the account is already the sole assignee, starting or
resuming verifies and retains that assignment without rewriting it. A failed
read, write or readback cannot yield a successful claim.

An issue assigned only to another member is unavailable to the current member.
If an update races with another claim and the readback has a different or
additional assignee, report a conflict and stop implementation. Multiple
assignees permit work only after the current owner invites a named collaborator
and that collaborator accepts in GitHub issue comments attributed to their
authenticated accounts. The accepted collaboration then adds the collaborator
to the assignee field and verifies it. The field remains the ownership
authority; the comments distinguish agreement from a competing update that
happened to produce the same field. A handoff explicitly names the incoming
member, confirms the current owner, updates the GitHub field without removing
unrelated assignees, and verifies the result. Relinquishing ownership is an
explicit action; ending a session or pausing work preserves the assignment.
Closed issues retain their historical accountable assignee unless an authorized
handoff or relinquishment changes it.

At `peer-work survey --when start`, surface open issues assigned to the current
member as recommended work to start or resume. Show issues assigned only to
others as occupied and keep them out of selectable work. Before beginning
implementation and again before publishing a branch or PR for an issue, the
project guidance requires a fresh assignee check. If ownership changed, the
agent stops issue work and reports the changed authority. This boundary cannot
prevent an unrelated client from changing assignees immediately afterward;
every participant must honor the same rule.

Use the existing authenticated GitHub provider and bounded API calls for reads
and writes. Mutating commands require the same explicit external-write
authorization used elsewhere in the CLI. Never log credential material. A
project on another forge reports this ownership mode as unsupported until a
forge-specific contract is accepted; it does not simulate GitHub assignment
with local state. Update the canonical development and survey skills, generated
project templates and CLI guidance together.

## Planning and acceptance

After the directing user accepts or amends this ADR, record a linked roadmap
item for the 1.5.0 planning release before implementation. Its evidence
must include actual GitHub assignment and readback for an unassigned issue,
same-member resume in a new session, recommendations for assigned open issues,
another member's refused claim, explicit handoff and collaboration, and failed
or conflicting claim refusal. Test the API and guidance boundaries with
controlled fixtures, then verify the real provider path and exact-head source,
installed-wheel and platform gates. No local marker or mock-only test counts as
proof that GitHub assignees changed.

## Consequences

Issue ownership becomes visible across people, sessions and machines through
the forge field already used by maintainers. Starting work may require a forge
write before editing source, and inaccessible GitHub state stops that work.
Concurrent writers can still race because GitHub supplies no atomic claim;
readback, conflict refusal and repeated checks make the limitation observable
without claiming a lock that does not exist.

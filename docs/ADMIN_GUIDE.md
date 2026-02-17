# System Administrator Guide (Admin)

Documentation HQ: [README](../README.md)

This guide is for the Admin role—the persona responsible for system stability and maintaining the execution quality of OKRs across the organization.

**Goal:**

- Ensure the system is always available.
- Provide a smooth user experience.
- Keep data secure and recoverable.
- Drive strategic decisions based on the "Big Picture."

---

## 1) What is the Admin's Role?

The Admin doesn't just have "more access"; they are responsible for "System Quality":

- Data integrity.
- Access security.
- Service continuity.
- Disaster recovery (Backup / Restore).
- Alignment of team execution with top-level goals.

---

## 2) Admin Daily Routine (10-minute check)

1. Check app status (ensure services are up).
2. Verify the active `OKR Cycle`.
3. Review the Global Dashboard for:
   - `Needs care` items.
   - High-risk KRs.
   - Teams/Individuals requiring follow-up.
4. Run `AI Progress Sync` if needed to refresh strategic analyses.

---

## 3) Sustainable Admin Schedule

### Daily

- Monitor app health and critical errors.
- Handle user access requests.
- Quickly review critical delays.

### Weekly

- Review Weekly Reports and team rituals.
- Check Retros for recurring patterns.
- Refine top-level priorities (don't just fight fires).
- Test backup recovery (at least in a staging environment).

### Monthly

- Audit Cycle structure and OKR quality.
- Clean up access/ownership ambiguities.
- Perform a light security audit (passwords, permissions, workflows).

---

## 4) Using the Admin Panel Effectively

The `Admin Panel` has several critical sections:

### User List

- Monitor active/inactive status.
- Audit roles.
- Identify unused or suspicious accounts.

### Create User

- Assign the correct role from the start.
- Assign a manager (for team visibility flows).
- Enforce password change on first login.

### Reset Password

- Only for actual support scenarios.
- Enable `Require change at next login` after a reset.

### DB Backup

- `Prepare Backup File` for a full logical export.
- `Restore Backup` only with explicit, informed consent.
- **Warning:** Restore replaces all current data.

---

## 5) AI Governance & Intelligence

As an Admin, you oversee the quality of system insights. `AI Progress Sync` is your tool for:

- Refreshing strategic analysis across the entire organization.
- Identifying "Red Flags" that might be hidden by manual reporting.
- Aligning reported progress with actual execution reality.

> [!IMPORTANT]
> Admin oversight is critical for AI quality. Ensure users provide descriptive task titles and time estimates.
> Detailed AI logic and best practices can be found in the **[AI Features Guide](AI_FEATURES_GUIDE.md)**.

---

## 6) Backup & Restore: Operational Method

### Export (Weekly Recommended)

1. Admin Panel > `DB Backup`.
2. `Prepare Backup File`.
3. `Download Backup`.
4. Store the file securely (named with the date).

### Import (Emergency / Migration)

1. Always take a fresh backup of the current state first.
2. Upload the backup file.
3. Confirm full data overwrite.
4. Run Restore.
5. Post-restore tests: Login, Focus Map, Inspector, Timer.

---

## 7) Reports, Rituals, & Retros

If these three areas are disciplined:

- **Reports** = Execution reality (no guessing).
- **Rituals** = Decision discipline.
- **Retros** = Organizational learning.

Result: The team moves from reactive to proactive, and quality improves over time.

---

## 8) Golden Rule for Admins

A successful Admin doesn't just fix bugs; they keep the organization in a sustainable rhythm:

`Clear Focus` + `Regular Execution` + `Honest Reflection` + `Fast Correction`

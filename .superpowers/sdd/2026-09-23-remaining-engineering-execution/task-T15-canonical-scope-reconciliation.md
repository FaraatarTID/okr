# T15 canonical C6 scope reconciliation

## Finding

The C6 register called every uncovered item a route and required each listed
route to be visited. Repository inspection shows alignment is an Inspector
surface and RTL is rendered text styling, not a route. The current E2E test
also directly visits fewer routes than the historical evidence line implies.

## Correction

Updated the C6 evidence, deliverable, and acceptance to distinguish path routes
from UI states. T15 must assert actual route-specific UI for route flows and
rendered alignment/RTL states for the non-route surfaces. The approved T15
packet now says the same and requires correct role policy and isolated test data.

## Scope

Only C6's canonical register row, the T15 execution-plan row, and this report
were changed. No E2E test, app code, or status closure was changed. T15 remains
open and awaits implementation after T12's final access review.

## Review refinement

The independent scope review passed and requested a directly executable
role/surface matrix. The C6 and T15 rows now specify non-admin route visits for
admin/manager/member, admin-only users/teams/backup/audit coverage, manager
Cycles-only access, direct member Admin denial assertions, and direct-load
deep-link state. A second review confirmed the matrix and isolated test data,
then requested that direct-load deep-link verification appear in C6's
acceptance itself; that phrase is now included. This strengthens the existing
acceptance without changing T15 status or inventing roles/routes.

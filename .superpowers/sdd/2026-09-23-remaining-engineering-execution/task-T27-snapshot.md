diff --git a/scripts/verify_rollback_evidence.py b/scripts/verify_rollback_evidence.py
index 1039bc4..bdb774a 100644
--- a/scripts/verify_rollback_evidence.py
+++ b/scripts/verify_rollback_evidence.py
@@ -302,6 +302,17 @@ def verify_rollback_record(
         "observed_at",
     ):
         _required_string(execution.get(field), f"rollback record.execution.{field}")
+    observed_at = execution["observed_at"]
+    try:
+        observed_at_parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
+    except ValueError as exc:
+        raise RollbackEvidenceError(
+            "rollback record.execution.observed_at must be an ISO-8601 timestamp"
+        ) from exc
+    if observed_at_parsed.tzinfo is None:
+        raise RollbackEvidenceError(
+            "rollback record.execution.observed_at must include a timezone"
+        )
     if execution.get("healthcheck") != "PASSED":
         raise RollbackEvidenceError(
             "rollback record.execution.healthcheck must be PASSED"
diff --git a/tests/test_rollback_evidence.py b/tests/test_rollback_evidence.py
index 8f222f5..0793cab 100644
--- a/tests/test_rollback_evidence.py
+++ b/tests/test_rollback_evidence.py
@@ -180,10 +180,32 @@ def test_verifies_final_production_rollback_record() -> None:
         ("rollback_from_manifest_run_id", "", "manifest run ID"),
         ("approved_by", "", "approved by"),
         ("approved_at", "not-a-timestamp", "approved at"),
+        (
+            "execution",
+            {
+                "status": "SUCCESS",
+                "target_environment_id": "env-acme",
+                "provider_operation_id": "darkube-rollback-20260902-001",
+                "healthcheck": "PASSED",
+                "observed_at": "not-a-timestamp",
+            },
+            "observed_at",
+        ),
+        (
+            "execution",
+            {
+                "status": "SUCCESS",
+                "target_environment_id": "env-acme",
+                "provider_operation_id": "darkube-rollback-20260902-001",
+                "healthcheck": "PASSED",
+                "observed_at": "2026-09-02T10:21:00",
+            },
+            "timezone",
+        ),
     ],
 )
 def test_rejects_invalid_final_production_rollback_record(
-    field: str, value: str, message: str
+    field: str, value: object, message: str
 ) -> None:
     manifest = valid_manifest()
     record = {
diff --git a/tests/test_rollback_workflow_wiring.py b/tests/test_rollback_workflow_wiring.py
index e8e186a..b734d2c 100644
--- a/tests/test_rollback_workflow_wiring.py
+++ b/tests/test_rollback_workflow_wiring.py
@@ -186,3 +186,9 @@ def test_post_deployment_workflow_validates_the_completed_record() -> None:
     assert "workflow_dispatch" in (workflow.get("on") or {})
     verifier_steps = _verifier_steps(workflow)
     assert any("--record" in _run(step) for step in verifier_steps)
+    attach_step = next(
+        step
+        for step in _steps(workflow)
+        if step.get("name") == "Attach the provider execution outcome"
+    )
+    assert ".execution = $execution" in _run(attach_step)

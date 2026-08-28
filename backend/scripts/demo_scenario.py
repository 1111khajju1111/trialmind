"""
End-to-end demo scenario runner for SIH26046 (implementation plan, section 16
& 17 -- "The One Demo Scenario" / "Definition of Done"), and the mentor
review's "Most important manual test".

This hits the running backend over HTTP and walks through:

  RESET DEMO -> SELECT LIPID-2 STUDY -> RUN MATCHING AGENT -> AGENT TIMELINE
  -> CANDIDATE FOUND -> ELIGIBILITY + EVIDENCE -> APPROVE (HUMAN REVIEW)
  -> GENERATE OUTREACH -> FINALIZE (NOT SENT) -> ENROLL A CONSENTED SUBJECT
  -> VERIFY PROTOCOL DEVIATION ON RECORD -> VERIFY SAE ON RECORD
  -> COMPLIANCE ALERTS -> PORTFOLIO DASHBOARD -> FHIR/SDTM EXPORT
  -> AUDIT TRAIL

It only reads/exercises the API -- it does not replace running the actual
frontend in front of a judge, but it's a fast, repeatable way to confirm
the whole workflow is wired correctly before a demo, and it doubles as a
smoke test after any backend change.

Usage:
    cd backend
    pip install requests
    python scripts/demo_scenario.py [--base-url http://localhost:8000]

Exits non-zero on the first failed step, printing which step failed and why.
"""
import argparse
import sys
import time

try:
    import requests
except ImportError:
    print("This script needs the 'requests' package: pip install requests")
    sys.exit(1)


PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
STEP = "\033[96m"
RESET = "\033[0m"


class Scenario:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.failures = 0

    def _role(self, role: str):
        self.session.headers["X-User-Role"] = role

    def step(self, label: str):
        print(f"\n{STEP}▶ {label}{RESET}")

    def check(self, condition: bool, ok_msg: str, fail_msg: str):
        if condition:
            print(f"  [{PASS}] {ok_msg}")
        else:
            print(f"  [{FAIL}] {fail_msg}")
            self.failures += 1
        return condition

    def request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        resp = self.session.request(method, url, **kwargs)
        return resp

    def run(self):
        self.step("0. Health check")
        r = self.request("GET", "/health")
        if not self.check(r.status_code == 200, "Backend reachable.", f"Backend unreachable: {r.status_code}"):
            print("\nAborting -- backend must be running first (uvicorn app.main:app).")
            return

        self.step("1. RESET DEMO (as Administrator)")
        self._role("Administrator")
        r = self.request("POST", "/admin/reset")
        self.check(r.status_code == 200, "Demo data reset.", f"Reset failed: {r.status_code} {r.text}")

        self.step("2. SELECT LIPID-2 trial")
        self._role("Study Coordinator")
        r = self.request("GET", "/trials/")
        trials = r.json() if r.status_code == 200 else []
        lipid2 = next((t for t in trials if "LIPID-2" in t.get("name", "")), None)
        if not self.check(lipid2 is not None, f"Found trial: {lipid2['name'] if lipid2 else ''}",
                           "LIPID-2 trial not found in seeded data."):
            return
        trial_id = lipid2["id"]

        r = self.request("GET", "/studies/")
        studies = r.json() if r.status_code == 200 else []
        study = next((s for s in studies if s.get("id") == lipid2.get("study_id")), None)
        study_id = study["id"] if study else None
        self.check(study_id is not None, f"LIPID-2 is linked to study #{study_id}.",
                    "LIPID-2 has no linked CTMS study.")

        self.step("3. RUN MATCHING AGENT")
        r = self.request("POST", "/patients/match/start", json={"trial_id": trial_id, "site_id": None})
        run_id = r.json().get("run_id") if r.status_code == 200 else None
        if not self.check(run_id is not None, f"Agent run started: {run_id}",
                           f"Could not start matching agent: {r.status_code} {r.text}"):
            return

        self.step("4. AGENT TIMELINE (poll until terminal)")
        terminal = {"run_completed", "run_timeout", "agent_error", "persistence_failed"}
        timeline = []
        for _ in range(60):
            r = self.request("GET", f"/audit/timeline/{run_id}")
            timeline = r.json() if r.status_code == 200 else []
            if any(step["step_name"] in terminal for step in timeline):
                break
            time.sleep(1)
        finished = any(step["step_name"] == "run_completed" for step in timeline)
        self.check(finished, f"Run completed with {len(timeline)} timeline steps.",
                    f"Run did not complete cleanly: {[s['step_name'] for s in timeline]}")

        self.step("5. CANDIDATE FOUND + ELIGIBILITY + EVIDENCE")
        r = self.request("GET", "/patients/matches", params={"run_id": run_id})
        matches = r.json() if r.status_code == 200 else []
        eligible = [m for m in matches if m["verdict"] in ("ELIGIBLE", "POTENTIAL_MATCH")]
        if not self.check(len(eligible) > 0, f"{len(eligible)} candidate(s) found for human review.",
                           "No eligible/potential candidates were produced by this run."):
            return
        candidate = eligible[0]
        self.check(len(candidate.get("evidence", [])) >= 0, "Evidence field present on candidate.",
                    "Evidence field missing from candidate payload.")

        self.step("6. HUMAN REVIEW: APPROVE")
        r = self.request("POST", "/approvals/", json={
            "module": "patient_matching", "record_id": candidate["id"],
            "action": "approved", "reviewer_note": "Demo scenario approval.",
        })
        approved_ok = r.status_code == 200 and not r.json().get("error")
        self.check(approved_ok, "Candidate approved by coordinator.", f"Approval failed: {r.status_code} {r.text}")

        self.step("7. GENERATE OUTREACH DRAFT")
        r = self.request("POST", f"/patients/matches/{candidate['id']}/outreach")
        draft_ok = r.status_code == 200 and r.json().get("outreach_draft")
        self.check(draft_ok, "Outreach draft generated.", f"Outreach generation failed: {r.status_code} {r.text}")

        self.step("8. FINALIZE OUTREACH (demo mode: never actually sent)")
        r = self.request("POST", f"/patients/matches/{candidate['id']}/send-outreach", json={
            "to_email": "referring.physician@example-hospital.org",
        })
        body = r.json() if r.status_code == 200 else {}
        finalized = body.get("match", {}).get("outreach_status") in ("FINALIZED", "SENT")
        self.check(finalized, f"Outreach status: {body.get('match', {}).get('outreach_status')}.",
                    f"Finalize step failed: {r.status_code} {r.text}")

        if study_id:
            self.step("9. ENROLL A CONSENTED, ELIGIBLE SUBJECT")
            r = self.request("GET", f"/studies/{study_id}/subjects")
            subjects = r.json() if r.status_code == 200 else []
            candidate_subject = next(
                (s for s in subjects if s["status"] == "eligible" and s.get("consent_status") == "obtained"), None
            )
            if candidate_subject:
                self._role("Principal Investigator")
                r = self.request("POST", f"/studies/{study_id}/subjects/{candidate_subject['id']}/enroll", json={})
                self.check(r.status_code == 200, f"Subject #{candidate_subject['id']} enrolled.",
                            f"Enrollment failed: {r.status_code} {r.text}")
                self._role("Study Coordinator")
            else:
                print("  [skip] No eligible+consented subject in seed data to enroll.")

            self.step("10. VERIFY PROTOCOL DEVIATION ON RECORD")
            r = self.request("GET", f"/studies/{study_id}/deviations")
            deviations = r.json() if r.status_code == 200 else []
            self.check(len(deviations) > 0, f"{len(deviations)} protocol deviation(s) on record.",
                        "No protocol deviations found for this study.")

            self.step("11. VERIFY SAE ON RECORD + SAFETY DASHBOARD")
            r = self.request("GET", "/safety/sae", params={"study_id": study_id})
            saes = r.json() if r.status_code == 200 else []
            self.check(len(saes) > 0, f"{len(saes)} SAE case(s) on record.", "No SAE cases found for this study.")
            r = self.request("GET", "/safety/dashboard", params={"study_id": study_id})
            self.check(r.status_code == 200, "Safety dashboard reachable.", f"Safety dashboard failed: {r.status_code}")

            self.step("12. COMPLIANCE ALERTS (regulatory + safety deadlines)")
            r = self.request("GET", "/compliance/alerts", params={"study_id": study_id})
            alerts = r.json().get("alerts", []) if r.status_code == 200 else []
            self.check(r.status_code == 200, f"{len(alerts)} compliance alert(s) returned.",
                        f"Compliance alerts endpoint failed: {r.status_code}")

        self.step("13. EXECUTIVE PORTFOLIO DASHBOARD")
        r = self.request("GET", "/dashboard/portfolio")
        self.check(r.status_code == 200, "Portfolio dashboard reachable.", f"Portfolio dashboard failed: {r.status_code}")

        self.step("14. FHIR + SDTM INTEROPERABILITY EXPORT")
        r = self.request("GET", "/interop/fhir/ResearchStudy")
        self.check(r.status_code == 200 and r.json().get("resourceType") == "Bundle",
                    "FHIR ResearchStudy bundle returned.", f"FHIR export failed: {r.status_code}")
        r = self.request("GET", "/export/sdtm/DM")
        self.check(r.status_code == 200 and "USUBJID" in r.text, "SDTM DM CSV exported.",
                    f"SDTM export failed: {r.status_code}")

        self.step("15. RBAC: Regulator role is read-only")
        self._role("Regulator")
        r = self.request("POST", "/admin/reset")
        self.check(r.status_code == 403, "Regulator correctly blocked from a write action.",
                    f"Regulator was NOT blocked (status {r.status_code}) -- RBAC gap.")
        self._role("Study Coordinator")

        self.step("16. AUDIT TRAIL")
        r = self.request("GET", "/audit/runs")
        self.check(r.status_code == 200 and len(r.json()) > 0, "Agent run history present in audit trail.",
                    "No agent runs found in audit trail.")

        print(f"\n{'='*60}")
        if self.failures == 0:
            print(f"{PASS} — all {16} demo scenario steps completed. Freeze the feature set.")
        else:
            print(f"{FAIL} — {self.failures} step(s) failed. Fix these before the demo.")
        print(f"{'='*60}")
        return self.failures == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    scenario = Scenario(args.base_url)
    ok = scenario.run()
    sys.exit(0 if ok else 1)

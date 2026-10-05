"""Direct-mode tests for IssueBountyJudge (GitHub API, diff and LLM mocked)."""

import json

from tests.direct.conftest import to_hex

C = "contracts/issue_bounty_judge.py"
ISSUE = "https://github.com/acme/widgets/issues/7"
PR = "https://github.com/acme/widgets/pull/12"
CRITERIA = "Add a --dry-run flag to the CLI that prints actions without executing them, with a test."
API = r".*api\.github\.com/repos/acme/widgets/pulls/12.*"
DIFF = r".*patch-diff\.githubusercontent\.com.*"
JUDGE = r".*judging whether a merged GitHub pull request.*"


def _pr(merged=True, author="Bob-Dev"):
    body = {"merged": merged, "user": {"login": author}, "title": "Add --dry-run", "body": "Closes #7"}
    return {"status": 200, "body": json.dumps(body)}


def _setup(direct_vm, direct_deploy, maintainer, hunter, handle="bob-dev"):
    c = direct_deploy(C)
    direct_vm.sender = maintainer
    bid = c.post_bounty(ISSUE, CRITERIA, 500)
    direct_vm.sender = hunter
    idx = c.submit_claim(bid, PR, handle)
    return c, bid, idx


def _mock_ok(direct_vm, pr=None, verdict=True):
    direct_vm.mock_web(API, pr or _pr())
    direct_vm.mock_web(DIFF, {"status": 200, "body": "+ parser.add_argument('--dry-run')"})
    direct_vm.mock_llm(JUDGE, json.dumps({"meets_criteria": verdict, "reason": "Flag and test added."}))


def test_post_and_claim(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, bid, idx = _setup(direct_vm, direct_deploy, direct_alice, direct_bob)
    b = c.get_bounty(bid)
    assert bid == "bounty-1" and idx == 0
    assert b["repo"] == "acme/widgets"
    assert b["maintainer"] == to_hex(direct_alice)
    assert b["claims"][0]["claimant"] == to_hex(direct_bob)
    assert b["claims"][0]["status"] == "pending"


def test_input_validation(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(C)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Issue URL must be"):
        c.post_bounty("https://gitlab.com/a/b/issues/1", CRITERIA, 10)
    with direct_vm.expect_revert("Acceptance criteria too short"):
        c.post_bounty(ISSUE, "fix it", 10)
    bid = c.post_bounty(ISSUE, CRITERIA, 10)
    with direct_vm.expect_revert("Maintainer cannot claim own bounty"):
        c.submit_claim(bid, PR, "alice")
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("PR must be in the bounty's repository"):
        c.submit_claim(bid, "https://github.com/other/repo/pull/3", "bob")
    c.submit_claim(bid, PR, "bob")
    with direct_vm.expect_revert("PR already claimed"):
        c.submit_claim(bid, PR, "bob")


def test_resolve_awards_points(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, bid, idx = _setup(direct_vm, direct_deploy, direct_alice, direct_bob)
    _mock_ok(direct_vm)
    res = c.resolve(bid, idx)
    assert res["status"] == "awarded"
    b = c.get_bounty(bid)
    assert b["status"] == "awarded"
    assert b["winner"] == to_hex(direct_bob)
    assert c.get_points(to_hex(direct_bob)) == 500
    with direct_vm.expect_revert("Bounty is not open"):
        c.resolve(bid, idx)


def test_author_mismatch_rejected(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, bid, idx = _setup(direct_vm, direct_deploy, direct_alice, direct_bob, handle="thief")
    _mock_ok(direct_vm)
    res = c.resolve(bid, idx)
    assert res["status"] == "rejected"
    assert "author" in res["reason"]
    assert c.get_bounty(bid)["status"] == "open"
    assert c.get_points(to_hex(direct_bob)) == 0


def test_unmerged_reverts_and_criteria_fail(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, bid, idx = _setup(direct_vm, direct_deploy, direct_alice, direct_bob)
    _mock_ok(direct_vm, pr=_pr(merged=False))
    with direct_vm.expect_revert("PR not merged yet"):
        c.resolve(bid, idx)
    direct_vm.clear_mocks()
    _mock_ok(direct_vm, verdict=False)
    res = c.resolve(bid, idx)
    assert res["status"] == "rejected"
    assert c.get_bounty(bid)["status"] == "open"


def test_cancel_rules(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, bid, idx = _setup(direct_vm, direct_deploy, direct_alice, direct_bob)
    with direct_vm.expect_revert("Only the maintainer"):
        c.cancel_bounty(bid)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Resolve pending claims first"):
        c.cancel_bounty(bid)
    _mock_ok(direct_vm, verdict=False)
    c.resolve(bid, idx)
    c.cancel_bounty(bid)
    assert c.get_bounty(bid)["status"] == "cancelled"

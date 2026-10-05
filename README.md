# IssueBountyJudge

A GenLayer Intelligent Contract for **GitHub issue bounties that settle themselves**. A maintainer posts a bounty with plain-English acceptance criteria. A contributor claims it with their pull request. Anyone can then call `resolve`, and the contract checks the facts on GitHub and judges the diff against the criteria. No manual sign-off, and the maintainer can't quietly refuse to pay out.

## Why
Open-source bounties break down in two places:
1. **Trust in facts.** Is the PR merged? Did the claimant actually write it?
2. **Trust in judgement.** Does the change really do what the issue asked?

Traditional smart contracts can't do either. GenLayer can do both, and this contract uses **a different consensus principle for each**.

## Two-stage consensus
| Stage | What | Principle | Why |
|---|---|---|---|
| 1. Facts | GitHub REST API: `merged`, author `login`, title, description | `gl.eq_principle.strict_eq` | Objective data should get exact agreement |
| 2. Judgement | LLM reads the PR diff against the acceptance criteria and returns `{meets_criteria, reason}` | `gl.vm.run_nondet_unsafe` with a custom validator | Validators agree on the **boolean verdict** only. The free-text reason is stored but not compared, so different wording can't break consensus |

Stage 1 blocks the two classic exploits before any LLM runs:
- **Claiming someone else's PR.** The PR author must match the claimant's GitHub handle, otherwise the claim is permanently rejected.
- **Claiming early.** An unmerged PR reverts with *"PR not merged yet"*, and the claim stays pending so it can be resolved after merge.

The judging prompt tells the model to ignore instructions embedded in the PR title, description or diff, which protects against prompt injection.

## Flow
1. `post_bounty(issue_url, criteria, reward)`: the maintainer posts a bounty and gets back `bounty-N`.
2. `submit_claim(bounty_id, pr_url, github_handle)`: the PR must be in the same repo. Duplicate PRs and maintainer self-claims are rejected.
3. `resolve(bounty_id, claim_index)`: anyone can call it. It runs stage 1, then stage 2.
4. If the claim passes, the bounty is **awarded** and the claimant's on-chain contributor **points** go up by the reward. If it fails, the claim is **rejected** with a reason and the bounty stays open for other claims.
5. `cancel_bounty(bounty_id)`: the maintainer can cancel, but only when no claims are pending.

## Methods
| Method | Type |
|---|---|
| `post_bounty(issue_url, criteria, reward) -> str` | write |
| `submit_claim(bounty_id, pr_url, github_handle) -> int` | write |
| `resolve(bounty_id, claim_index) -> dict` | write (non-deterministic, two-stage) |
| `cancel_bounty(bounty_id)` | write, maintainer only |
| `get_bounty(bounty_id) -> dict` | view |
| `get_points(address) -> int` | view |
| `get_bounty_count() -> int` | view |

## Tests
```bash
pip install -r requirements.txt
genvm-lint check contracts/issue_bounty_judge.py
python -m pytest tests/direct -v
```
The six direct-mode tests mock the GitHub API, the diff and the LLM. They cover posting and claiming, URL, criteria and self-claim validation, a successful award with points credited, author-mismatch rejection, the unmerged revert followed by a criteria-fail rejection, and the cancel rules.

## Deployment
GenLayer Studio (studionet): see the explorer link in the submission.

## License
MIT

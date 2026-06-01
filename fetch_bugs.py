#!/usr/bin/env python3
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime

GITLAB_URL = os.environ.get('GITLAB_URL', 'https://git.enlight.dev')
TOKEN      = os.environ.get('GITLAB_TOKEN', '')
GROUP      = 'enlight360containers'
MILESTONE  = 'Upcoming'
CUTOFF     = datetime(2026, 4, 1)

BUG_LABELS = {
    'bug','Bug','Bug Type - Functional','Bug Type - UI','Bug Type - Integration',
    'Bug Type - Non Functional','Bug Type - Production','Bug Type - Validation',
    'Bug-Cloud UI','bug-closed','bug-duplicate','bug-fixed','bug-invalid',
    'bug-onhold','bug-reopen','bug-worksforme','Bug Fixing','ReOpen',
    'Severity-Blocker','Severity-Critical','Severity-Major','Severity-Normal','Severity-Minor',
    'Stage Injected - Coding','Stage Injected - Design','high-priority','medium-priority',
    'low-priority','Ready for QA'
}

PROJECT_DOMAIN_MAP = {
    'cloud-ui':'IaaS Platform','cloud-app':'IaaS Platform',
    'virtual-machine-user-interface':'IaaS Platform','network-ops-ui':'IaaS Platform',
    'quota-ui':'IaaS Platform','billing-ui':'IaaS Platform','billing-service':'IaaS Platform',
    'billing-user-interface':'IaaS Platform','ipam-app':'IaaS Platform',
    'ipam-service':'IaaS Platform','monitoring-app':'IaaS Platform','monitoring-service':'IaaS Platform',
    'ahcp-solutions-layer/ahcp-solutions-layer':'PaaS & Kubernetes',
    'ahcp-solutions-layer':'PaaS & Kubernetes','solution-layer-ui':'PaaS & Kubernetes',
    'solution-layer-keycloak-ui':'PaaS & Kubernetes','container-registry-ui':'PaaS & Kubernetes',
    'container-registry-service':'PaaS & Kubernetes','kaas-engine':'PaaS & Kubernetes',
    'kaas-service':'PaaS & Kubernetes','kaas-ui':'PaaS & Kubernetes','enlight-faas':'PaaS & Kubernetes',
    'market-place-ui':'Cloud Marketplace','marketplace-service':'Cloud Marketplace',
    'enlight-solution-provider':'Cloud Marketplace',
    'iam-app':'Developer Platform','iam-ui':'Developer Platform','api-gateway-app':'Developer Platform',
    'patch-ui':'Developer Platform','patch-service':'Developer Platform',
    'forecast-service':'Developer Platform','workflow-app':'Developer Platform',
    'enlight360-tracker':'Developer Platform','enlight-toolkit':'Developer Platform',
    'feedback-service':'Developer Platform','url-service':'Developer Platform',
    'siem-service':'SaaS Enablement','ad-app':'SaaS Enablement','ad-aas-app':'SaaS Enablement',
    'dbaas-app':'DBaaS & Data','grafana':'AI/ML Platform'
}

def api_get(path, params=None):
    url = f"{GITLAB_URL}/api/v4/{path}"
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'PRIVATE-TOKEN': TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def get_all_pages(path, params=None):
    params = params or {}
    params['per_page'] = 100
    results = []
    page = 1
    while True:
        params['page'] = page
        data = api_get(path, params)
        if not data:
            break
        results.extend(data)
        if len(data) < 100:
            break
        page += 1
    return results

def get_project(issue):
    ref = (issue.get('references') or {}).get('full', '')
    return ref.replace(f'{GROUP}/', '').split('#')[0]

def get_domain(issue):
    proj = get_project(issue)
    if proj in PROJECT_DOMAIN_MAP:
        return PROJECT_DOMAIN_MAP[proj]
    return PROJECT_DOMAIN_MAP.get(proj.split('/')[-1], 'Other')

def is_bug(issue):
    return bool(set(issue.get('labels', [])) & BUG_LABELS)

def get_stage(issue):
    labels = set(issue.get('labels', []))
    if labels & {'bug-fixed','Development Completed','Ready for QA'}: return 'Fixed'
    if labels & {'Bug Fixing','development','Development','Backend Dev','Frontend Dev',
                 'Engineering','frontend','backend','In Progress',
                 'Stage Injected - Coding','Stage Injected - Design'}: return 'In Dev'
    if labels & {'QA','QA: Testing'}: return 'In QA'
    if labels & {'bug-onhold','OnHold'}: return 'On Hold'
    if labels & {'bug-reopen','ReOpen'}: return 'Reopened'
    return 'Open'

def get_severity(issue):
    labels = issue.get('labels', [])
    for s in ['Severity-Blocker','Severity-Critical','Severity-Major','Severity-Normal','Severity-Minor']:
        if s in labels: return s.replace('Severity-','')
    if 'high-priority' in labels: return 'Critical'
    if 'medium-priority' in labels: return 'Major'
    if 'low-priority' in labels: return 'Minor'
    return '\u2014'

def get_bugtype(issue):
    labels = issue.get('labels', [])
    for b in ['Bug Type - Functional','Bug Type - UI','Bug Type - Integration',
              'Bug Type - Non Functional','Bug Type - Validation','Bug Type - Production']:
        if b in labels: return b.replace('Bug Type - ','')
    return '\u2014'

def fmt_date(s):
    if not s: return '\u2014'
    try:
        d = datetime.fromisoformat(s.replace('Z','').replace('+00:00',''))
        return d.strftime('%d %b %Y')
    except: return '\u2014'

def serialize(issue, state):
    assignee = issue.get('assignee') or {}
    return {
        'iid': issue.get('iid',''),
        'title': issue.get('title',''),
        'project': get_project(issue),
        'domain': get_domain(issue),
        'state': state,
        'stage': get_stage(issue),
        'severity': get_severity(issue),
        'bugtype': get_bugtype(issue),
        'assignee': assignee.get('name','\u2014'),
        'url': issue.get('web_url',''),
        'created': fmt_date(issue.get('created_at','')),
    }

def main():
    if not TOKEN:
        print("ERROR: GITLAB_TOKEN not set")
        exit(1)

    print(f"Fetching projects from {GROUP}...")
    projects = get_all_pages(f'groups/{GROUP}/projects', {'include_subgroups': 'true'})
    print(f"Found {len(projects)} projects")

    records = []
    for proj in projects:
        pid = proj['id']
        print(f"  Fetching: {proj['name']}")
        try:
            for state in ['opened','closed']:
                issues = get_all_pages(f'projects/{pid}/issues', {
                    'milestone_title': MILESTONE, 'state': state
                })
                st = 'open' if state == 'opened' else 'closed'
                for issue in issues:
                    if not is_bug(issue): continue
                    try:
                        created = datetime.fromisoformat(issue['created_at'].replace('Z','').replace('+00:00',''))
                        if created < CUTOFF: continue
                    except: continue
                    records.append(serialize(issue, st))
        except Exception as e:
            print(f"    Warning: {e}")

    open_count   = sum(1 for r in records if r['state'] == 'open')
    closed_count = sum(1 for r in records if r['state'] == 'closed')
    print(f"\nTotal bugs: {len(records)} (open={open_count}, closed={closed_count})")

    # Save to root (GitHub Pages serves from root)
    with open('bug_data.json', 'w') as f:
        json.dump(records, f)
    print("Written: bug_data.json")

    now = datetime.utcnow().strftime('%d %b %Y %H:%M UTC')
    with open('last_updated.txt', 'w') as f:
        f.write(now)
    print(f"Last updated: {now}")

if __name__ == '__main__':
    main()

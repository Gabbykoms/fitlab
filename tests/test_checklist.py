"""No-key tests for the checklist checker (spec.md section 8.1, behaviors G-1 to G-7)."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from checklist import check_checklist, disagreements, extract_json, text_matches  # noqa: E402

REQS = [
    'There is a faceless display mannequin, not a real person',
    'The mannequin wears hiking boots',
    'There is a placard on a stand beside the mannequin',
]


def critique_with(*met):
    return {'checks': [{'requirement': r, 'met': m, 'evidence': 'seen'} for r, m in zip(REQS, met)]}


def test_all_met_is_ok():
    assert check_checklist(REQS, critique_with(True, True, True)) == {
        'ok': True, 'problems': [], 'unmet': [], 'missing': [], 'extra': []}


def test_g1_not_json_is_a_failed_critique():
    result = check_checklist(REQS, extract_json('I am unable to view images.'))
    assert not result['ok']
    assert result['missing'] == REQS


def test_g1_json_without_checks_is_a_failed_critique():
    result = check_checklist(REQS, {'overall': 90})
    assert not result['ok']
    assert result['missing'] == REQS


def test_g2_json_inside_prose_and_fences_is_extracted():
    text = 'Sure!\n```json\n{"checks": [{"requirement": "a", "met": true}]}\n```\nDone.'
    assert extract_json(text) == {'checks': [{'requirement': 'a', 'met': True}]}
    assert extract_json(None) is None
    assert extract_json('{"checks": [ broken') is None


def test_g3_unanswered_requirement_is_a_problem():
    partial = {'checks': [{'requirement': REQS[0], 'met': True}, {'requirement': REQS[2], 'met': True}]}
    result = check_checklist(REQS, partial)
    assert not result['ok']
    assert result['missing'] == [REQS[1]]


def test_g4_invented_requirement_is_a_problem():
    critique = critique_with(True, True, True)
    critique['checks'].append({'requirement': 'The outfit is stylish', 'met': True})
    result = check_checklist(REQS, critique)
    assert not result['ok']
    assert result['extra'] == ['The outfit is stylish']


def test_g5_unmet_is_named_and_only_true_counts():
    assert check_checklist(REQS, critique_with(True, False, True))['unmet'] == [REQS[1]]
    assert check_checklist(REQS, critique_with(True, 'yes', True))['unmet'] == [REQS[1]]


def test_requirement_text_matched_after_normalizing():
    critique = {'checks': [{'requirement': r.lower() + '.', 'met': True} for r in REQS]}
    assert check_checklist(REQS, critique)['ok']


def test_g6_expected_text_is_compared_in_code():
    assert text_matches('HIKE', ' hike. ')
    assert text_matches('GAME DAY', 'Game-Day')
    assert not text_matches('HIKE', 'HIIKE')
    assert not text_matches('HIKE', '')
    assert not text_matches('HIKE', None)


def test_g7_disagreements_between_two_critics():
    a = [{'name': 'occasion-02', 'critique': critique_with(True, True, True), 'text_read': 'HIIKE'}]
    b = [{'name': 'occasion-02', 'critique': critique_with(True, False, True), 'text_read': 'HIKE'}]
    diffs = disagreements(a, b)
    assert len(diffs) == 1
    assert {d['requirement'] for d in diffs[0]['diffs']} == {REQS[1], '<text read>'}
    assert disagreements(a, a) == []

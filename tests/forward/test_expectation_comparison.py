from copy import deepcopy
import pytest
from src.forward.expectation_comparison import compare_metric, ledger_comparisons, AXES
from src.forward.performance_report import calculate_report


def matched():
    # Explicit test-only prospectively saved estimate, not a real user forecast.
    definition = {'start':'2026-10-01','end':'2026-10-02','currency':'KRW',
        'cost_basis':'TRANSACTION_COSTS_INCLUDED','dividend_basis':'PROVIDER_ADJUSTED_OR_CLOSE',
        'return_definition':'NAV_CHANGE_NO_EXTERNAL_FLOWS','sampling':'OBSERVED_ENDPOINTS',
        'portfolio_reference':'test-judgment','benchmark_reference':'NONE'}
    return {'value':.01,'unit':'fraction','definition':definition}, {
        'value':.02,'unit':'fraction','definition':deepcopy(definition)}


def test_same_period_fraction_difference_and_direction():
    expected, actual = matched()
    result = compare_metric('expected_return', expected, actual)
    assert result['status'] == 'COMPARABLE'
    assert result['difference'] == pytest.approx(.01)
    assert result['difference_direction'] == 'ACTUAL_MINUS_EXPECTED'
    assert result['difference_unit'] == 'fraction'
    assert result['reasons'] == []


@pytest.mark.parametrize('axis', ['unit', *AXES])
def test_each_definition_mismatch_prevents_subtraction(axis):
    expected, actual = matched()
    if axis == 'unit':
        expected['unit'] = 'percent'
    else:
        expected['definition'][axis] = 'different'
    result = compare_metric('expected_return', expected, actual)
    assert result['status'] == 'NOT_COMPARABLE' and result['difference'] is None
    assert axis.upper() + '_DIFFERS' in result['reasons']


def test_legacy_never_reconstructs_basis_and_real_zero_is_comparable():
    expected, actual = matched()
    original = {'value':.01,'unit':'fraction'}
    result = compare_metric('expected_return', original, actual)
    assert result['difference'] is None and 'ORIGINAL_COMPARISON_BASIS_NOT_RECORDED' in result['reasons']
    assert original == {'value':.01,'unit':'fraction'}
    expected['value'] = actual['value'] = 0
    assert compare_metric('expected_return', expected, actual)['difference'] == 0
    expected['value'] = None
    assert compare_metric('expected_return', expected, actual)['difference'] is None


def test_existing_finance_report_drives_numeric_comparison():
    expected, _ = matched()
    report = calculate_report([{'date':'2026-10-01','nav':100,'cash':100},
                               {'date':'2026-10-02','nav':102,'cash':102}], [], [], [])
    result = ledger_comparisons({'expected_return':expected}, report, 'test-judgment', 'CORE_V0.3')[0]
    assert result['difference'] == pytest.approx(.01)
    assert report['metrics']['volatility'] is None


def test_annual_return_is_not_converted_and_risk_gaps_remain():
    expected, actual = matched()
    expected['unit'] = 'fraction_per_year'
    expected['definition']['sampling'] = 'annual_model'
    expected['definition']['cost_basis'] = 'EXCLUDES_TRANSACTION_COSTS'
    result = compare_metric('expected_return', expected, actual)
    assert result['difference'] is None
    assert {'UNIT_DIFFERS','SAMPLING_DIFFERS','COST_BASIS_DIFFERS'} <= set(result['reasons'])
    expected, actual = matched()
    actual['quality_reason'] = 'ACTUAL_RISK_OBSERVATION_GAPS'
    assert compare_metric('volatility', expected, actual)['difference'] is None

import {render,screen,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {HistoricalPreview} from '../dashboard/HistoricalPreview';
const response=vi.hoisted(()=>({data:null as any}));
vi.mock('@tanstack/react-query',()=>({useQuery:()=>response}));
afterEach(cleanup);
it('does not fabricate history when archive is absent',()=>{response.data={available:false};render(<HistoricalPreview/>);expect(screen.queryByRole('img')).toBeNull()});
it('separates historical performance and discloses carried source dates',()=>{
 response.data={available:true,report:{start:'2026-10-02',end:'2026-10-06',decision_confirmed_at:'2026-10-06T01:00Z',is_current_configuration:false,cost_bps:10,summary:{personal_return:.01,core_return:-.01,observations:2},series:[{date:'2026-10-02',personal_index:100,core_index:100},{date:'2026-10-06',personal_index:101,core_index:99}],price_dates:{'2026-10-05':{korea_equity:'2026-10-02'}}}};
 render(<HistoricalPreview/>);expect(screen.getByRole('img')).toHaveAccessibleName('모의운용 평가 지수 그래프');expect(screen.getByText('운용 기준일 2026.10.02')).toBeVisible();expect(screen.getByText(/사후 계산한 모의운용 결과/)).toBeInTheDocument();expect(screen.getByText('구성을 변경하기 전의 저장된 결과입니다.')).toBeVisible();expect(screen.getByText('계산 기준과 일별 값').closest('details')).not.toHaveAttribute('open');expect(screen.getByText(/korea_equity: 2026-10-02/)).toBeInTheDocument();
});
